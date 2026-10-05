"""Benchmark deterministic transformation of synthetic customer records."""

from __future__ import annotations

import argparse
import json
import resource
from pathlib import Path
from time import perf_counter, perf_counter_ns, process_time
from uuid import uuid4

from contracts.plan import PlanCreate
from contracts.schema import SchemaDefinition
from evaluation.calculate_metrics import percentile
from services.target_check import transform_and_check_record


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def example(name: str):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def benchmark(count: int) -> dict:
    target_schema = SchemaDefinition.model_validate(example("customer_target_schema.json"))
    plan = PlanCreate.model_validate({
        "source_schema_version_id": str(uuid4()),
        "target_schema_version_id": str(uuid4()),
        "dataset_version_id": str(uuid4()),
        "name": "Synthetic transformation benchmark",
        "mappings": example("customer_mappings.json"),
    })
    template = example("customer_source_records.json")[0]
    latencies: list[float] = []
    accepted = 0
    wall_started = perf_counter()
    cpu_started = process_time()
    for index in range(count):
        record = {
            **template,
            "customer_id": str(100_000 + index),
            "email": f"SYNTHETIC{index}@EXAMPLE.COM",
        }
        started = perf_counter_ns()
        result = transform_and_check_record(
            plan=plan, source_record=record, target_schema=target_schema
        )
        latencies.append((perf_counter_ns() - started) / 1_000_000)
        accepted += int(result.valid)
    wall_seconds = perf_counter() - wall_started
    return {
        "records": count,
        "accepted": accepted,
        "rejected": count - accepted,
        "records_per_second": round(count / wall_seconds, 2),
        "wall_seconds": round(wall_seconds, 3),
        "cpu_seconds": round(process_time() - cpu_started, 3),
        "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        "record_latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p90": percentile(latencies, 0.90),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "evaluation" / "results" / "transform-benchmark" / "summary.json",
    )
    args = parser.parse_args()
    if any(count < 1 or count > 10000 for count in args.counts):
        parser.error("each count must be between 1 and 10,000")
    results = [benchmark(count) for count in args.counts]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
