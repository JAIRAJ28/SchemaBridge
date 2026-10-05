"""Aggregate SchemaBridge case scores into evaluation metrics."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from evaluation.compare_results import f1_score, read_jsonl, safe_divide


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(rows)
    successful = sum(row["prediction_status"] == "success" for row in rows)
    timeouts = sum(row["prediction_status"] == "timeout" for row in rows)
    mapping_tp = sum(row["mapping"]["true_positive"] for row in rows)
    mapping_predicted = sum(row["mapping"]["predicted"] for row in rows)
    mapping_expected = sum(row["mapping"]["expected"] for row in rows)
    mapping_precision = safe_divide(mapping_tp, mapping_predicted)
    mapping_recall = safe_divide(mapping_tp, mapping_expected)
    risk_tp = sum(row["risks"]["true_positive"] for row in rows)
    risk_predicted = sum(row["risks"]["predicted"] for row in rows)
    risk_expected = sum(row["risks"]["expected"] for row in rows)
    risk_precision = safe_divide(risk_tp, risk_predicted)
    risk_recall = safe_divide(risk_tp, risk_expected)
    record_tp = sum(row["records"]["accepted_true_positive"] for row in rows)
    record_fp = sum(row["records"]["accepted_false_positive"] for row in rows)
    record_fn = sum(row["records"]["accepted_false_negative"] for row in rows)
    record_precision = safe_divide(record_tp, record_tp + record_fp)
    record_recall = safe_divide(record_tp, record_tp + record_fn)
    latencies = [
        float(row["latency_ms"])
        for row in rows
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    dry_runs = sum(row["records"]["dry_run_evaluated"] for row in rows)
    expected_dry_runs = sum(row["records"]["dry_run_expected"] for row in rows)
    payload_matches = sum(row["records"]["payload_matches"] for row in rows)
    payload_total = sum(row["records"]["payload_total"] for row in rows)
    plan_checks = sum(row["plan_validity"]["evaluated"] for row in rows)
    return {
        "case_count": case_count,
        "successful_case_count": successful,
        "failed_case_count": case_count - successful,
        "timeout_count": timeouts,
        "success_rate": safe_divide(successful, case_count),
        "mapping": {
            "precision": mapping_precision,
            "recall": mapping_recall,
            "f1": f1_score(mapping_precision, mapping_recall),
            "exact_plan_accuracy": safe_divide(
                sum(row["exact_plan"] for row in rows), case_count
            ),
            "exact_mapping_accuracy": safe_divide(
                sum(row["mapping"]["exact"] for row in rows), case_count
            ),
            "rule_selection_accuracy": safe_divide(
                sum(row["rules"]["correct"] for row in rows),
                sum(row["rules"]["expected"] for row in rows),
            ),
            "proposal_status_accuracy": safe_divide(
                sum(row["proposal_status_correct"] for row in rows), case_count
            ),
        },
        "clarification_accuracy": safe_divide(
            sum(row["clarification"]["correct"] for row in rows), case_count
        ),
        "risk": {
            "precision": risk_precision,
            "recall": risk_recall,
            "f1": f1_score(risk_precision, risk_recall),
        },
        "hallucination_rate": safe_divide(
            sum(row["hallucination"]["items"] for row in rows),
            sum(row["hallucination"]["references"] for row in rows),
        ),
        "plan_validity_accuracy": safe_divide(
            sum(row["plan_validity"]["correct"] for row in rows), plan_checks
        ),
        "record_acceptance": {
            "precision": record_precision,
            "recall": record_recall,
            "f1": f1_score(record_precision, record_recall),
            "dry_run_coverage": safe_divide(dry_runs, expected_dry_runs),
            "payload_match_rate": safe_divide(payload_matches, payload_total),
            "count_match_rate": safe_divide(
                sum(row["records"]["counts_match"] for row in rows), dry_runs
            ),
        },
        "latency_ms": {
            "mean": mean(latencies) if latencies else None,
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_difficulty[row["difficulty"]].append(row)
        by_category[row["category"]].append(row)
    return {
        "overall": aggregate(rows),
        "by_difficulty": {
            name: aggregate(items) for name, items in sorted(by_difficulty.items())
        },
        "by_category": {
            name: aggregate(items) for name, items in sorted(by_category.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = build_summary(read_jsonl(args.scores))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["overall"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
