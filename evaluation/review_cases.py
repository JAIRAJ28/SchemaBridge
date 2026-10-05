"""Inspect candidate labels and record explicit human review decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation.compare_results import read_jsonl, write_jsonl


ROOT = Path(__file__).resolve().parent
CASE_FILES = (ROOT / "gold_cases.jsonl", ROOT / "gold_full_record_cases.jsonl")
REVIEWS_FILE = ROOT / "reviews.jsonl"


def case_hash(case: dict) -> str:
    content = json.dumps(
        {"input": case["input"], "expected": case["expected"]},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def load_reviewed_cases() -> list[dict]:
    cases = [case for path in CASE_FILES for case in read_jsonl(path)]
    reviews = {
        item["case_id"]: item
        for item in read_jsonl(REVIEWS_FILE)
    } if REVIEWS_FILE.exists() else {}
    for case in cases:
        review = reviews.get(case["case_id"])
        if review and review["case_hash"] == case_hash(case):
            case["review"] = {
                "status": review["decision"],
                "reviewer": review["reviewer"],
                "reviewed_at": review["reviewed_at"],
                "note": review.get("note"),
            }
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--status", action="store_true")
    action.add_argument("--next", action="store_true")
    action.add_argument("--sample", type=int, metavar="COUNT")
    action.add_argument("--show", metavar="CASE_ID")
    action.add_argument("--approve", metavar="CASE_ID")
    action.add_argument("--reject", metavar="CASE_ID")
    parser.add_argument("--reviewer")
    parser.add_argument("--note")
    args = parser.parse_args()

    cases = load_reviewed_cases()
    if args.status:
        print(json.dumps(dict(Counter(case["review"]["status"] for case in cases)), indent=2))
        return
    if args.next:
        pending = next(
            (case for case in cases if case["review"]["status"] == "pending_human_review"),
            None,
        )
        if pending is None:
            print("No pending cases.")
        else:
            print(pending["case_id"])
        return
    if args.sample is not None:
        if args.sample < 1:
            parser.error("--sample must be at least 1")
        seen = set()
        for case in cases:
            if case["category"] not in seen:
                print(case["case_id"])
                seen.add(case["category"])
                if len(seen) == args.sample:
                    break
        return
    case_id = args.show or args.approve or args.reject
    case = next((item for item in cases if item["case_id"] == case_id), None)
    if case is None:
        parser.error(f"Case not found: {case_id}")
    if args.show:
        print(json.dumps(case, indent=2, ensure_ascii=False))
        return
    if not args.reviewer or not args.reviewer.strip():
        parser.error("--reviewer is required for a decision")
    if args.reject and not args.note:
        parser.error("--note is required when rejecting a case")

    reviews = read_jsonl(REVIEWS_FILE) if REVIEWS_FILE.exists() else []
    reviews = [item for item in reviews if item["case_id"] != case_id]
    reviews.append({
        "case_id": case_id,
        "case_hash": case_hash(case),
        "decision": "approved" if args.approve else "rejected",
        "reviewer": args.reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "note": args.note,
    })
    write_jsonl(REVIEWS_FILE, sorted(reviews, key=lambda item: item["case_id"]))
    print(f"Recorded {reviews[-1]['decision']} review for {case_id}.")


if __name__ == "__main__":
    main()
