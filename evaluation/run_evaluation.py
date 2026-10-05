"""Run SchemaBridge gold cases through the configured AI and score them."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain_core.messages import HumanMessage, SystemMessage
from contracts.agent_result import AgentPlanProposal
from contracts.plan import PlanCreate
from contracts.schema import SchemaDefinition
from evaluation.calculate_metrics import build_summary
from evaluation.compare_results import compare_cases, read_jsonl, write_jsonl
from evaluation.review_cases import load_reviewed_cases
from services.agent_flow import SYSTEM_PROMPT, request_proposal
from services.ai_model import get_proposal_model
from services.dataset_check import (
    RecordToCheck,
    business_key_hash,
    check_dataset_keys,
)
from services.plan_check import check_plan
from services.rule_list import RULE_LIST_VERSION, list_rules
from services.target_check import transform_and_check_record


ROOT = Path(__file__).resolve().parent
def load_cases(dataset: str) -> list[dict[str, Any]]:
    cases = load_reviewed_cases()
    if dataset == "original":
        cases = [case for case in cases if case.get("suite", "original") == "original"]
    elif dataset == "full":
        cases = [case for case in cases if case.get("suite") == "full_record_json"]
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Selected datasets contain duplicate case IDs.")
    return cases


def supported_rules_context() -> dict[str, Any]:
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
    }


def case_ids(case_id: str) -> dict[str, str]:
    return {
        "source_schema_version_id": str(uuid5(NAMESPACE_URL, f"{case_id}:source")),
        "target_schema_version_id": str(uuid5(NAMESPACE_URL, f"{case_id}:target")),
        "dataset_version_id": str(uuid5(NAMESPACE_URL, f"{case_id}:dataset")),
    }


def normalize_proposal(value: Any) -> dict[str, Any]:
    proposal = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    return {
        "proposal_status": proposal["status"],
        "mappings": proposal.get("mappings", []),
        "questions": proposal.get("questions", []),
        "risks": proposal.get("risks", []),
        "missing_source_fields": proposal.get("missing_source_fields", []),
        "incompatible_fields": proposal.get("incompatible_fields", []),
    }


def execute_proposal(
    case: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    if proposal.get("proposal_status") == "needs_clarification":
        return {"plan_valid": None, "plan_problems": [], "dry_run": None}

    ids = case_ids(case["case_id"])
    try:
        plan = PlanCreate.model_validate(
            {
                **ids,
                "name": f"Evaluation plan for {case['case_id']}",
                "description": "Generated during offline evaluation.",
                "mappings": proposal.get("mappings", []),
            }
        )
        source_schema = SchemaDefinition.model_validate(
            case["input"]["source_schema"]
        )
        target_schema = SchemaDefinition.model_validate(
            case["input"]["target_schema"]
        )
    except Exception as error:
        return {
            "plan_valid": False,
            "plan_problems": [
                {
                    "code": "PLAN_CONTRACT_INVALID",
                    "message": f"{type(error).__name__}: {error}"[:1000],
                }
            ],
            "dry_run": None,
        }

    validation = check_plan(
        plan=plan,
        source_schema=source_schema,
        target_schema=target_schema,
    )
    if not validation.valid:
        return {
            "plan_valid": False,
            "plan_problems": [
                item.model_dump(mode="json") for item in validation.problems
            ],
            "dry_run": None,
        }

    transformed: list[RecordToCheck] = []
    for ordinal, record in enumerate(case["input"]["source_records"]):
        transformed.append(
            RecordToCheck(
                source_record_id=uuid5(
                    NAMESPACE_URL, f"{case['case_id']}:evaluation-row:{ordinal}"
                ),
                row_ordinal=ordinal,
                result=transform_and_check_record(
                    plan=plan,
                    source_record=record,
                    target_schema=target_schema,
                ),
            )
        )
    existing_hashes = {
        business_key_hash(value)
        for value in case["input"].get("existing_target_business_keys", [])
    }
    checked = check_dataset_keys(
        records=transformed,
        target_schema=target_schema,
        existing_target_key_hashes=existing_hashes,
    )
    records: list[dict[str, Any]] = []
    transformed_count = 0
    accepted_count = 0
    for item in checked:
        problems = [
            problem.model_dump(mode="json") for problem in item.result.problems
        ]
        transformed_count += int(
            not any(problem["stage"] == "transformation" for problem in problems)
        )
        accepted = item.result.valid
        accepted_count += int(accepted)
        records.append(
            {
                "row_ordinal": item.row_ordinal,
                "status": "accepted" if accepted else "rejected",
                "transformed_record": item.result.model_dump(mode="json")[
                    "transformed_record"
                ],
                "error_codes": [problem["code"] for problem in problems],
                "field_errors": problems,
            }
        )
    source_count = len(records)
    return {
        "plan_valid": True,
        "plan_problems": [],
        "dry_run": {
            "source_count": source_count,
            "transformed_count": transformed_count,
            "accepted_count": accepted_count,
            "rejected_count": source_count - accepted_count,
            "records": records,
        },
    }


async def predict_with_ai(
    case: dict[str, Any],
    *,
    model: Any,
    model_name: str,
    rules_context: dict[str, Any],
    output_schema: dict[str, Any] | None,
    request_timeout_seconds: int,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    ids = case_ids(case["case_id"])
    context = {
        "authorized_input_versions": ids,
        "source_schema": case["input"]["source_schema"],
        "target_schema": case["input"]["target_schema"],
        "sample_records": case["input"]["source_records"],
        "existing_target_business_keys": case["input"].get(
            "existing_target_business_keys", []
        ),
        "supported_rules": rules_context,
    }
    if output_schema is not None:
        context["required_output_schema"] = output_schema
    started = perf_counter()
    try:
        async with semaphore:
            value, attempts = await request_proposal(
                model,
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            "Prepare a migration plan from this evaluation context. "
                            "Use the exact authorized version IDs and return only the "
                            "required proposal structure:\n\n"
                            + json.dumps(context, ensure_ascii=False, default=str)
                        )
                    ),
                ],
                timeout_seconds=request_timeout_seconds,
            )
        proposal = normalize_proposal(value)
        return {
            "case_id": case["case_id"],
            "status": "success",
            "mode": "ai",
            "model": model_name,
            "latency_ms": round((perf_counter() - started) * 1000, 3),
            "model_attempts": attempts,
            "proposal": proposal,
            "execution": execute_proposal(case, proposal),
            "error": None,
        }
    except Exception as error:
        name = type(error).__name__
        timed_out = "timeout" in name.casefold() or "timeout" in str(error).casefold()
        return {
            "case_id": case["case_id"],
            "status": "timeout" if timed_out else "error",
            "mode": "ai",
            "model": model_name,
            "latency_ms": round((perf_counter() - started) * 1000, 3),
            "proposal": None,
            "execution": None,
            "error": {"type": name, "message": str(error)[:1000]},
        }


def predict_from_gold(case: dict[str, Any]) -> dict[str, Any]:
    proposal = case["expected"]["agent"]
    return {
        "case_id": case["case_id"],
        "status": "success",
        "mode": "gold",
        "model": "gold-label-pipeline-check",
        "latency_ms": None,
        "proposal": proposal,
        "execution": execute_proposal(case, proposal),
        "error": None,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    from config.settings import get_settings

    settings = get_settings()
    structured_method = args.structured_method or settings.ai_structured_method
    cases = load_cases(args.dataset)
    if args.one_per_category:
        seen: set[str] = set()
        selected = []
        for case in cases:
            if case["category"] not in seen:
                seen.add(case["category"])
                selected.append(case)
        cases = selected
    if args.limit is not None:
        cases = cases[: args.limit]
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "predictions.jsonl"
    prior = read_jsonl(predictions_path) if args.resume and predictions_path.exists() else []
    prior_by_id = {
        item["case_id"]: item for item in prior
        if item.get("status") == "success"
    }
    pending = [case for case in cases if case["case_id"] not in prior_by_id]

    new_predictions: list[dict[str, Any]]
    model_name = "gold-label-pipeline-check"
    if args.mode == "gold":
        new_predictions = [predict_from_gold(case) for case in pending]
    else:
        model_name = settings.ai_model
        model = get_proposal_model(
            timeout_seconds=args.request_timeout_seconds,
            max_retries=args.max_retries,
            structured_method=structured_method,
        )
        semaphore = asyncio.Semaphore(args.concurrency)
        rules_context = supported_rules_context()
        output_schema = (
            AgentPlanProposal.model_json_schema()
            if structured_method == "json_mode" else None
        )
        new_predictions = list(
            await asyncio.gather(
                *[
                    predict_with_ai(
                        case,
                        model=model,
                        model_name=model_name,
                        rules_context=rules_context,
                        output_schema=output_schema,
                        request_timeout_seconds=(
                            args.request_timeout_seconds or settings.ai_timeout_seconds
                        ),
                        semaphore=semaphore,
                    )
                    for case in pending
                ]
            )
        )

    prediction_by_id = {
        **prior_by_id,
        **{item["case_id"]: item for item in new_predictions},
    }
    predictions = [prediction_by_id[case["case_id"]] for case in cases]
    write_jsonl(predictions_path, predictions)
    scores = compare_cases(cases, predictions)
    scores_path = output_dir / "case_scores.jsonl"
    write_jsonl(scores_path, scores)
    summary = build_summary(scores)
    review_status_counts = Counter(
        case.get("review", {}).get("status", "unknown") for case in cases
    )
    summary["run"] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "model": model_name,
        "dataset": args.dataset,
        "rule_list_version": RULE_LIST_VERSION,
        "structured_method": structured_method,
        "case_count": len(cases),
        "resumed_case_count": len(cases) - len(pending),
        "new_case_count": len(pending),
        "label_review_status_counts": dict(sorted(review_status_counts.items())),
        "official_gold_evaluation": (
            args.mode == "ai" and set(review_status_counts) == {"approved"}
        ),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "predictions": str(predictions_path),
        "case_scores": str(scores_path),
        "summary": str(summary_path),
        "overall": summary["overall"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("gold", "ai"), default="gold")
    parser.add_argument(
        "--dataset", choices=("original", "full", "all"), default="all"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--one-per-category", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1, choices=range(1, 21))
    parser.add_argument(
        "--request-timeout-seconds", type=int, default=None
    )
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument(
        "--structured-method",
        choices=("json_schema", "function_calling", "json_mode"),
        default=None,
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "results" / "latest"
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.request_timeout_seconds is not None and args.request_timeout_seconds < 1:
        parser.error("--request-timeout-seconds must be at least 1")
    if args.max_retries is not None and not 0 <= args.max_retries <= 5:
        parser.error("--max-retries must be between 0 and 5")
    return args


def main() -> None:
    result = asyncio.run(run(parse_args()))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
