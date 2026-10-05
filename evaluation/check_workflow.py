"""Run a synthetic API walkthrough against a locally running SchemaBridge."""

from __future__ import annotations

import argparse
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text

from config.settings import get_settings
from evaluation.calculate_metrics import percentile


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def read_example(name: str):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def run(base_url: str, include_ai: bool, inject_conflict: bool = False) -> dict:
    timings: list[dict] = []
    token = None
    with httpx.Client(base_url=base_url, timeout=180) as client:
        def call(label: str, method: str, path: str, *, body=None, key=None):
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            if key:
                headers["Idempotency-Key"] = key
            started = perf_counter()
            response = client.request(
                method, path, json=body, headers=headers,
            )
            elapsed = round((perf_counter() - started) * 1000, 3)
            timings.append({"step": label, "latency_ms": elapsed, "status": response.status_code})
            if not response.is_success:
                raise RuntimeError(
                    f"{label} failed: HTTP {response.status_code}: {response.text[:300]}"
                )
            return response.json()

        account = call("register", "POST", "/auth/register", body={
            "email": f"workflow-{uuid4().hex}@example.com",
            "display_name": "Synthetic Reviewer",
            "password": secrets.token_urlsafe(24),
        })
        token = account["access_token"]
        project = call("project", "POST", "/projects", body={
            "name": "Synthetic customer workflow check",
            "target_namespace": f"review_{uuid4().hex[:12]}",
        })
        project_id = project["id"]
        source = call("source_schema", "POST", f"/projects/{project_id}/schemas",
                      body=read_example("customer_source_schema.json"))
        target = call("target_schema", "POST", f"/projects/{project_id}/schemas",
                      body=read_example("customer_target_schema.json"))
        dataset = call(
            "dataset", "POST",
            f"/projects/{project_id}/datasets?source_schema_snapshot_id={source['id']}",
            body=read_example("customer_source_records.json"),
        )
        call("profile", "POST", f"/projects/{project_id}/datasets/{dataset['id']}/profile")

        agent_status = "skipped"
        agent_result_valid = None
        agent_question_count = 0
        if include_ai:
            try:
                agent = call("agent", "POST", f"/projects/{project_id}/agent-runs", body={
                    "dataset_id": dataset["id"],
                    "source_schema_id": source["id"],
                    "target_schema_id": target["id"],
                })
                agent_status = agent["status"]
                questions = call(
                    "agent_questions", "GET",
                    f"/projects/{project_id}/agent-runs/{agent['id']}/questions",
                )
                agent_question_count = len(questions)
                if agent_status == "ready_for_review" and agent.get("plan_id"):
                    ai_dry_run = call(
                        "agent_dry_run", "POST",
                        f"/projects/{project_id}/plans/{agent['plan_id']}/dry-runs",
                    )
                    ai_records = call(
                        "agent_dry_run_records", "GET",
                        f"/projects/{project_id}/plans/{agent['plan_id']}/dry-runs/{ai_dry_run['id']}/records",
                    )["items"]
                    agent_result_valid = (
                        ai_dry_run["accepted_count"] == 1
                        and ai_dry_run["rejected_count"] == 1
                        and ai_records[0]["transformed_record"].get("email_address")
                        == "alex.example@example.com"
                        and ai_records[0]["transformed_record"].get("country") == "IN"
                    )
            except RuntimeError as error:
                agent_status = str(error)[:200]

        plan = call("reviewed_plan", "POST", f"/projects/{project_id}/plans", body={
            "source_schema_version_id": source["id"],
            "target_schema_version_id": target["id"],
            "dataset_version_id": dataset["id"],
            "name": "Synthetic reviewed mappings",
            "mappings": read_example("customer_mappings.json"),
        })
        dry_run = call("dry_run", "POST", f"/projects/{project_id}/plans/{plan['id']}/dry-runs")
        records = call(
            "dry_run_records", "GET",
            f"/projects/{project_id}/plans/{plan['id']}/dry-runs/{dry_run['id']}/records",
        )["items"]
        assert dry_run["source_count"] == 2
        assert dry_run["accepted_count"] == 1
        assert dry_run["rejected_count"] == 1
        assert [row["status"] for row in records] == ["accepted", "rejected"]
        assert records[0]["transformed_record"]["email_address"] == "alex.example@example.com"
        assert records[0]["transformed_record"]["country"] == "IN"
        assert any(
            error["code"] == "DECIMAL_PARSE_FAILED"
            for error in records[1]["field_errors"]
        )

        # This approval belongs only to this synthetic smoke-test account.
        approval = call(
            "synthetic_approval", "POST",
            f"/projects/{project_id}/plans/{plan['id']}/dry-runs/{dry_run['id']}/approval",
            body={"decision": "approved", "comment": "Synthetic workflow check"},
        )
        execution_key = str(uuid4())
        execute_path = f"/projects/{project_id}/approvals/{approval['id']}/execute"
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(call, "execute", "POST", execute_path, key=execution_key)
            second = executor.submit(call, "concurrent_retry", "POST", execute_path, key=execution_key)
            migration = first.result()
            retried = second.result()
        assert retried["id"] == migration["id"]
        assert retried["inserted_count"] == 1
        lost_response_retry = call("lost_response_retry", "POST", execute_path, key=execution_key)
        assert lost_response_retry["id"] == migration["id"]
        reconcile_path = f"/projects/{project_id}/migration-runs/{migration['id']}/reconcile"
        reconciliation = call("reconcile", "POST", reconcile_path)
        assert reconciliation["valid"] is True
        reconciliation_details = reconciliation["details"]
        mismatch_detected = None
        rollback_conflict_detected = None
        if inject_conflict:
            engine = create_engine(get_settings().database_url.get_secret_value())
            with engine.begin() as connection:
                target_row = connection.execute(
                    text("SELECT id, record_data FROM target_records WHERE migration_run_id = :run_id"),
                    {"run_id": migration["id"]},
                ).one()
                original_data = target_row.record_data
                changed_data = {**original_data, "city": "Tampered Synthetic City"}
                connection.execute(
                    text("UPDATE target_records SET record_data = CAST(:data AS jsonb) WHERE id = :id"),
                    {"data": json.dumps(changed_data), "id": target_row.id},
                )
            try:
                mismatched = call("reconcile_mismatch", "POST", reconcile_path)
                mismatch_detected = mismatched["valid"] is False
                conflicted = call(
                    "rollback_conflict", "POST",
                    f"/projects/{project_id}/migration-runs/{migration['id']}/rollback",
                )
                rollback_conflict_detected = conflicted["status"] == "rollback_conflict"
                assert mismatch_detected and rollback_conflict_detected
            finally:
                with engine.begin() as connection:
                    connection.execute(
                        text("UPDATE target_records SET record_data = CAST(:data AS jsonb) WHERE id = :id"),
                        {"data": json.dumps(original_data), "id": target_row.id},
                    )
                engine.dispose()
        attempts = call(
            "attempts", "GET",
            f"/projects/{project_id}/migration-runs/{migration['id']}/attempts",
        )
        rolled_back = call(
            "rollback", "POST",
            f"/projects/{project_id}/migration-runs/{migration['id']}/rollback",
        )
        assert rolled_back["status"] == "rolled_back"
        after_rollback = call("reconcile_after_rollback", "POST", reconcile_path)
        assert after_rollback["valid"] is True
        history = call("history", "GET", f"/projects/{project_id}/history")

    latencies = [item["latency_ms"] for item in timings]
    api_latencies = [
        item["latency_ms"] for item in timings if item["step"] != "agent"
    ]
    dry_run_ms = next(item["latency_ms"] for item in timings if item["step"] == "dry_run")
    return {
        "status": "passed" if not include_ai or agent_result_valid else "partial",
        "agent_status": agent_status,
        "agent_result_valid": agent_result_valid,
        "agent_question_count": agent_question_count,
        "checks": {
            "source_count": dry_run["source_count"],
            "accepted_count": dry_run["accepted_count"],
            "rejected_count": dry_run["rejected_count"],
            "inserted_count": migration["inserted_count"],
            "duplicate_insertion_count": retried["inserted_count"] - migration["inserted_count"],
            "lost_response_retry_same_run": lost_response_retry["id"] == migration["id"],
            "reconciliation_valid": reconciliation["valid"],
            "expected_target_count": reconciliation_details["expected_target_count"],
            "actual_target_count": reconciliation_details["actual_target_count"],
            "payload_hash_mismatch_count": len(reconciliation_details["hash_mismatch_source_ids"]),
            "rollback_valid": after_rollback["valid"],
            "mismatch_detected": mismatch_detected,
            "rollback_conflict_detected": rollback_conflict_detected,
            "history_event_count": len(history),
            "attempt_count": len(attempts),
        },
        "api_latency_ms": {
            "sample_count": len(api_latencies),
            "p50": percentile(api_latencies, 0.50),
            "p90": percentile(api_latencies, 0.90),
            "p95": percentile(api_latencies, 0.95),
            "p99": percentile(api_latencies, 0.99),
        },
        "workflow_latency_ms": round(sum(latencies), 3),
        "dry_run_records_per_second": round(2000 / dry_run_ms, 3),
        "request_timings": timings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--inject-conflict", action="store_true")
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "evaluation" / "results" / "workflow-check" / "summary.json",
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    if args.inject_conflict and args.workers != 1:
        parser.error("--inject-conflict requires --workers 1")
    if args.workers == 1:
        report = run(
            args.base_url,
            include_ai=not args.skip_ai,
            inject_conflict=args.inject_conflict,
        )
    else:
        started = perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            reports = list(executor.map(
                lambda _: run(args.base_url, include_ai=not args.skip_ai),
                range(args.workers),
            ))
        latencies = [
            step["latency_ms"]
            for item in reports
            for step in item["request_timings"]
            if step["step"] != "agent"
        ]
        report = {
            "status": "passed" if all(item["status"] == "passed" for item in reports) else "partial",
            "concurrent_migrations": args.workers,
            "passed_migrations": sum(item["status"] == "passed" for item in reports),
            "checks": {
                "source_count": sum(item["checks"]["source_count"] for item in reports),
                "accepted_count": sum(item["checks"]["accepted_count"] for item in reports),
                "rejected_count": sum(item["checks"]["rejected_count"] for item in reports),
                "inserted_count": sum(item["checks"]["inserted_count"] for item in reports),
                "duplicate_insertion_count": sum(item["checks"]["duplicate_insertion_count"] for item in reports),
                "reconciliation_valid": all(item["checks"]["reconciliation_valid"] for item in reports),
                "expected_target_count": sum(item["checks"]["expected_target_count"] for item in reports),
                "actual_target_count": sum(item["checks"]["actual_target_count"] for item in reports),
                "payload_hash_mismatch_count": sum(item["checks"]["payload_hash_mismatch_count"] for item in reports),
                "rollback_valid": all(item["checks"]["rollback_valid"] for item in reports),
            },
            "api_latency_ms": {
                "sample_count": len(latencies),
                "p50": percentile(latencies, 0.50),
                "p90": percentile(latencies, 0.90),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
            },
            "wall_seconds": round(perf_counter() - started, 3),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "request_timings"}, indent=2))


if __name__ == "__main__":
    main()
