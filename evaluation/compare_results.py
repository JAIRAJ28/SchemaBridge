"""Compare SchemaBridge predictions with expected evaluation labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from services.rule_list import RULES


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            output.write("\n")


def mapping_key(item: dict[str, Any]) -> tuple[tuple[str, ...], str]:
    return tuple(item.get("source_fields", [])), item.get("target_field", "")


def canonical_rules(item: dict[str, Any]) -> str:
    return json.dumps(
        item.get("rules", []),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_mappings(items: list[dict[str, Any]]) -> list[str]:
    return sorted(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in items
    )


def safe_divide(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def f1_score(precision: float, recall: float) -> float:
    return safe_divide(2 * precision * recall, precision + recall)


def score_case(
    case: dict[str, Any],
    prediction: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_agent = case["expected"]["agent"]
    predicted_agent = (prediction or {}).get("proposal") or {}
    expected_mappings = expected_agent.get("mappings", [])
    predicted_mappings = predicted_agent.get("mappings", [])

    expected_by_key = {mapping_key(item): item for item in expected_mappings}
    predicted_by_key = {mapping_key(item): item for item in predicted_mappings}
    matched_keys = set(expected_by_key) & set(predicted_by_key)
    mapping_tp = len(matched_keys)
    mapping_precision = safe_divide(mapping_tp, len(predicted_by_key))
    mapping_recall = safe_divide(mapping_tp, len(expected_by_key))

    rule_correct = sum(
        canonical_rules(expected_by_key[key]) == canonical_rules(predicted_by_key[key])
        for key in expected_by_key
        if key in predicted_by_key
    )
    rule_total = len(expected_by_key)

    source_fields = {
        field["name"] for field in case["input"]["source_schema"]["fields"]
    }
    target_fields = {
        field["name"] for field in case["input"]["target_schema"]["fields"]
    }
    hallucinated_items = 0
    referenced_items = 0
    for item in predicted_mappings:
        for source_field in item.get("source_fields", []):
            referenced_items += 1
            hallucinated_items += int(source_field not in source_fields)
        referenced_items += 1
        hallucinated_items += int(item.get("target_field") not in target_fields)
        for rule in item.get("rules", []):
            referenced_items += 1
            hallucinated_items += int(rule.get("rule") not in RULES)

    expected_questions = expected_agent.get("questions", [])
    predicted_questions = predicted_agent.get("questions", [])
    expected_clarification = any(
        item.get("blocking", True) for item in expected_questions
    )
    predicted_clarification = any(
        item.get("blocking", True) for item in predicted_questions
    )

    expected_risks = {item.get("code") for item in expected_agent.get("risks", [])}
    predicted_risks = {item.get("code") for item in predicted_agent.get("risks", [])}
    expected_risks.discard(None)
    predicted_risks.discard(None)
    risk_tp = len(expected_risks & predicted_risks)

    exact_mappings = canonical_mappings(expected_mappings) == canonical_mappings(
        predicted_mappings
    )
    expected_status = expected_agent.get("proposal_status")
    predicted_status = predicted_agent.get("proposal_status")
    status_correct = expected_status == predicted_status
    exact_plan = all(
        (
            exact_mappings,
            status_correct,
            set(expected_agent.get("missing_source_fields", []))
            == set(predicted_agent.get("missing_source_fields", [])),
            set(expected_agent.get("incompatible_fields", []))
            == set(predicted_agent.get("incompatible_fields", [])),
            expected_clarification == predicted_clarification,
        )
    )

    expected_dry_run = case["expected"].get("dry_run")
    predicted_execution = (prediction or {}).get("execution") or {}
    predicted_dry_run = predicted_execution.get("dry_run")
    record_counts = {
        "accepted_true_positive": 0,
        "accepted_false_positive": 0,
        "accepted_false_negative": 0,
        "accepted_true_negative": 0,
        "payload_matches": 0,
        "payload_total": 0,
        "dry_run_expected": int(expected_dry_run is not None),
        "dry_run_evaluated": 0,
        "counts_match": 0,
    }
    if expected_dry_run is not None and predicted_dry_run is not None:
        predicted_rows = {
            row["row_ordinal"]: row for row in predicted_dry_run.get("records", [])
        }
        for expected_row in expected_dry_run.get("records", []):
            predicted_row = predicted_rows.get(expected_row["row_ordinal"])
            expected_accepted = expected_row["status"] == "accepted"
            predicted_accepted = bool(
                predicted_row and predicted_row.get("status") == "accepted"
            )
            if expected_accepted and predicted_accepted:
                record_counts["accepted_true_positive"] += 1
            elif not expected_accepted and predicted_accepted:
                record_counts["accepted_false_positive"] += 1
            elif expected_accepted and not predicted_accepted:
                record_counts["accepted_false_negative"] += 1
            else:
                record_counts["accepted_true_negative"] += 1
            record_counts["payload_total"] += 1
            if predicted_row is not None:
                record_counts["payload_matches"] += int(
                    expected_row.get("transformed_record")
                    == predicted_row.get("transformed_record")
                    and expected_row.get("error_codes", [])
                    == predicted_row.get("error_codes", [])
                )
        record_counts["dry_run_evaluated"] = 1
        record_counts["counts_match"] = int(
            all(
                expected_dry_run.get(name) == predicted_dry_run.get(name)
                for name in (
                    "source_count",
                    "transformed_count",
                    "accepted_count",
                    "rejected_count",
                )
            )
        )

    expected_plan = case["expected"].get("plan")
    predicted_plan_valid = predicted_execution.get("plan_valid")
    plan_validity_evaluated = int(
        expected_plan is not None and predicted_plan_valid is not None
    )
    plan_validity_correct = int(
        plan_validity_evaluated
        and expected_plan.get("valid") == predicted_plan_valid
    )

    return {
        "case_id": case["case_id"],
        "dataset_version": case["dataset_version"],
        "suite": case.get("suite", "original"),
        "difficulty": case["difficulty"],
        "category": case["category"],
        "prediction_status": (prediction or {}).get("status", "missing"),
        "latency_ms": (prediction or {}).get("latency_ms"),
        "mapping": {
            "true_positive": mapping_tp,
            "predicted": len(predicted_by_key),
            "expected": len(expected_by_key),
            "precision": mapping_precision,
            "recall": mapping_recall,
            "f1": f1_score(mapping_precision, mapping_recall),
            "exact": int(exact_mappings),
        },
        "rules": {"correct": rule_correct, "expected": rule_total},
        "proposal_status_correct": int(status_correct),
        "exact_plan": int(exact_plan),
        "clarification": {
            "expected": int(expected_clarification),
            "predicted": int(predicted_clarification),
            "correct": int(expected_clarification == predicted_clarification),
        },
        "risks": {
            "true_positive": risk_tp,
            "predicted": len(predicted_risks),
            "expected": len(expected_risks),
        },
        "hallucination": {
            "items": hallucinated_items,
            "references": referenced_items,
        },
        "plan_validity": {
            "evaluated": plan_validity_evaluated,
            "correct": plan_validity_correct,
        },
        "records": record_counts,
        "error": (prediction or {}).get("error"),
    }


def compare_cases(
    cases: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prediction_by_id = {item["case_id"]: item for item in predictions}
    return [score_case(case, prediction_by_id.get(case["case_id"])) for case in cases]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scores = compare_cases(read_jsonl(args.cases), read_jsonl(args.predictions))
    write_jsonl(args.output, scores)
    print(json.dumps({"scored_cases": len(scores), "output": str(args.output)}))


if __name__ == "__main__":
    main()
