from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import SchemaRole
from contracts.plan import PlanCreate
from contracts.rule import RuleStep
from contracts.schema import SchemaDefinition
from repositories.data_summary_db import (
    get_latest_dataset_profile,
)
from repositories.dataset_db import (
    get_dataset_snapshot_by_id,
    list_source_records,
)
from repositories.dry_run_db import (
    get_target_key_hashes,
)
from repositories.schema_db import (
    get_schema_snapshot_by_id,
)
from services.dataset_check import business_key_hash
from services.plan_check import check_plan
from services.rule_list import (
    RULE_LIST_VERSION,
    list_rules,
)
from services.target_check import (
    transform_and_check_record,
)


MAX_AGENT_SAMPLE_RECORDS = 20
MAX_CONFLICT_KEYS = 200


@dataclass(frozen=True)
class AgentToolContext:
    project_id: UUID
    dataset_id: UUID
    source_schema_id: UUID
    target_schema_id: UUID


class AgentTools:
    def __init__(
        self,
        *,
        session: AsyncSession,
        context: AgentToolContext,
    ) -> None:
        self.session = session
        self.context = context

    async def _get_source_schema(
        self,
    ) -> SchemaDefinition:
        snapshot = await get_schema_snapshot_by_id(
            self.session,
            project_id=self.context.project_id,
            schema_snapshot_id=self.context.source_schema_id,
        )

        if (
            snapshot is None
            or snapshot.schema_role
            != SchemaRole.SOURCE.value
        ):
            raise ValueError(
                "Source schema was not found."
            )

        return SchemaDefinition.model_validate(
            snapshot.normalized_schema
        )

    async def _get_target_schema(
        self,
    ) -> SchemaDefinition:
        snapshot = await get_schema_snapshot_by_id(
            self.session,
            project_id=self.context.project_id,
            schema_snapshot_id=self.context.target_schema_id,
        )

        if (
            snapshot is None
            or snapshot.schema_role
            != SchemaRole.TARGET.value
        ):
            raise ValueError(
                "Target schema was not found."
            )

        return SchemaDefinition.model_validate(
            snapshot.normalized_schema
        )

    async def _check_dataset(
        self,
    ) -> None:
        dataset = await get_dataset_snapshot_by_id(
            self.session,
            project_id=self.context.project_id,
            dataset_id=self.context.dataset_id,
        )

        if dataset is None:
            raise ValueError(
                "Dataset was not found."
            )

        if (
            dataset.source_schema_snapshot_id
            != self.context.source_schema_id
        ):
            raise ValueError(
                "Dataset does not use the selected source schema."
            )

    async def inspect_source_schema(
        self,
    ) -> dict:
        source_schema = await self._get_source_schema()

        return source_schema.model_dump(
            mode="json"
        )

    async def inspect_target_schema(
        self,
    ) -> dict:
        target_schema = await self._get_target_schema()

        return target_schema.model_dump(
            mode="json"
        )

    async def profile_source_dataset(
        self,
    ) -> dict:
        await self._check_dataset()

        profile = await get_latest_dataset_profile(
            self.session,
            dataset_id=self.context.dataset_id,
        )

        if profile is None:
            raise ValueError(
                "Dataset profile was not found."
            )

        if profile.status != "completed":
            raise ValueError(
                "Dataset profile is not completed."
            )

        return {
            "profile_version": profile.profile_version,
            "summary": profile.summary,
            "field_statistics": profile.field_statistics,
            "duplicate_summary": profile.duplicate_summary,
            "profile_hash": profile.profile_hash,
        }

    async def sample_source_records(
        self,
        *,
        limit: int = 5,
    ) -> list[dict]:
        await self._check_dataset()

        if limit < 1 or limit > MAX_AGENT_SAMPLE_RECORDS:
            raise ValueError(
                "Sample limit must be between 1 and "
                f"{MAX_AGENT_SAMPLE_RECORDS}."
            )

        records = await list_source_records(
            self.session,
            dataset_id=self.context.dataset_id,
            offset=0,
            limit=limit,
        )

        return [
            {
                "row_ordinal": record.row_ordinal,
                "source_record_id": record.source_record_id,
                "record": record.canonical_record,
                "schema_valid": record.schema_valid,
            }
            for record in records
        ]

    def list_supported_transformations(
        self,
    ) -> dict:
        rule_schema = TypeAdapter(
            RuleStep
        ).json_schema()

        return {
            "rule_list_version": RULE_LIST_VERSION,
            "rules": [
                {
                    "name": rule.name,
                    "purpose": rule.purpose,
                    "minimum_inputs": rule.minimum_inputs,
                    "maximum_inputs": rule.maximum_inputs,
                }
                for rule in list_rules()
            ],
            "rule_parameter_schema": rule_schema,
        }

    async def inspect_target_conflicts(
        self,
        *,
        keys: list[Any],
    ) -> dict:
        if len(keys) > MAX_CONFLICT_KEYS:
            raise ValueError(
                "Too many target keys were requested."
            )

        existing_hashes = await get_target_key_hashes(
            self.session,
            project_id=self.context.project_id,
        )

        conflicts = [
            key
            for key in keys
            if business_key_hash(key)
            in existing_hashes
        ]

        return {
            "checked_count": len(keys),
            "conflict_count": len(conflicts),
            "conflicting_keys": conflicts,
        }

    async def validate_candidate_plan(
        self,
        *,
        plan_data: dict,
    ) -> dict:
        try:
            plan = PlanCreate.model_validate(
                plan_data
            )
        except ValidationError as error:
            return {
                "valid": False,
                "problems": error.errors(
                    include_url=False,
                    include_context=False,
                ),
            }

        if (
            plan.source_schema_version_id
            != self.context.source_schema_id
            or plan.target_schema_version_id
            != self.context.target_schema_id
            or plan.dataset_version_id
            != self.context.dataset_id
        ):
            return {
                "valid": False,
                "problems": [
                    {
                        "code": "INPUT_VERSION_MISMATCH",
                        "message": (
                            "The candidate plan does not use "
                            "the authorized input versions."
                        ),
                    }
                ],
            }

        source_schema = await self._get_source_schema()
        target_schema = await self._get_target_schema()

        result = check_plan(
            plan=plan,
            source_schema=source_schema,
            target_schema=target_schema,
        )

        return result.model_dump(
            mode="json"
        )

    async def preview_candidate_plan(
        self,
        *,
        plan_data: dict,
        limit: int = 5,
    ) -> dict:
        validation = await self.validate_candidate_plan(
            plan_data=plan_data
        )

        if not validation["valid"]:
            return {
                "valid": False,
                "plan_validation": validation,
                "records": [],
            }

        if limit < 1 or limit > MAX_AGENT_SAMPLE_RECORDS:
            raise ValueError(
                "Preview limit must be between 1 and "
                f"{MAX_AGENT_SAMPLE_RECORDS}."
            )

        plan = PlanCreate.model_validate(
            plan_data
        )
        target_schema = await self._get_target_schema()

        source_records = await list_source_records(
            self.session,
            dataset_id=self.context.dataset_id,
            offset=0,
            limit=limit,
        )

        preview_records: list[dict] = []

        for source_record in source_records:
            result = transform_and_check_record(
                plan=plan,
                source_record=(
                    source_record.canonical_record
                ),
                target_schema=target_schema,
            )

            preview_records.append(
                {
                    "row_ordinal": (
                        source_record.row_ordinal
                    ),
                    "source_record_id": (
                        source_record.source_record_id
                    ),
                    "result": result.model_dump(
                        mode="json"
                    ),
                }
            )

        return {
            "valid": True,
            "plan_validation": validation,
            "records": preview_records,
        }