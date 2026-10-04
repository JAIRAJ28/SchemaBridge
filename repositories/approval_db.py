from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_run import AgentQuestion, AgentRun
from models.approval import Approval
from models.project import MigrationProject


async def get_project_for_approval(
    session: AsyncSession,
    *,
    project_id: UUID,
    owner_id: str,
) -> MigrationProject | None:
    result = await session.execute(
        select(MigrationProject)
        .where(
            MigrationProject.id == project_id,
            MigrationProject.owner_id == owner_id,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def get_approval_by_dry_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    dry_run_id: UUID,
) -> Approval | None:
    result = await session.execute(
        select(Approval).where(
            Approval.project_id == project_id,
            Approval.dry_run_id == dry_run_id,
        )
    )
    return result.scalar_one_or_none()


async def get_approval_by_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    approval_id: UUID,
) -> Approval | None:
    result = await session.execute(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def has_unanswered_plan_questions(
    session: AsyncSession,
    *,
    plan_id: UUID,
) -> bool:
    result = await session.execute(
        select(
            exists().where(
                AgentRun.plan_id == plan_id,
                AgentQuestion.agent_run_id == AgentRun.id,
                AgentQuestion.blocking.is_(True),
                AgentQuestion.answer.is_(None),
            )
        )
    )
    return bool(result.scalar())


async def create_approval(
    session: AsyncSession,
    *,
    project_id: UUID,
    dry_run_id: UUID,
    plan_id: UUID,
    dataset_id: UUID,
    source_schema_id: UUID,
    target_schema_id: UUID,
    decision: str,
    bundle_fingerprint: str,
    bundle_data: dict,
    target_revision: int,
    rule_list_version: str,
    engine_version: str,
    policy_version: str,
    decided_by: str,
    comment: str | None,
) -> Approval:
    approval = Approval(
        project_id=project_id,
        dry_run_id=dry_run_id,
        plan_id=plan_id,
        dataset_id=dataset_id,
        source_schema_id=source_schema_id,
        target_schema_id=target_schema_id,
        decision=decision,
        bundle_fingerprint=bundle_fingerprint,
        bundle_data=bundle_data,
        target_revision=target_revision,
        rule_list_version=rule_list_version,
        engine_version=engine_version,
        policy_version=policy_version,
        decided_by=decided_by,
        comment=comment,
    )
    session.add(approval)
    await session.flush()
    await session.refresh(approval)
    return approval
