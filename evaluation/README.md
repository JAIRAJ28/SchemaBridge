# SchemaBridge Gold-Candidate Evaluation Dataset

This directory contains two deterministic synthetic evaluation suites with
2,000 total cases for the SchemaBridge AI planner and migration engine.

## Files

- `gold_cases.jsonl` contains one complete evaluation case per line.
- `gold_manifest.json` contains coverage and expected-result counts.
- `generate_gold_dataset.py` reproducibly generates and validates both files.
- `gold_full_record_cases.jsonl` contains 1,000 complete customer-JSON cases.
- `gold_full_record_manifest.json` contains full-record coverage totals.
- `generate_full_record_gold_dataset.py` generates the full-record suite.
- `run_evaluation.py` runs gold-pipeline checks or configured-model evaluation.
- `compare_results.py` scores each predicted proposal and deterministic dry run.
- `calculate_metrics.py` aggregates overall, difficulty and category metrics.

## Review status

The generated cases are **gold candidates**. Each case has
`review.status = pending_human_review`. A domain reviewer must confirm schemas,
mappings, questions, risks and expected record results before changing that
status to `approved`. Generated labels alone must not be presented as a
human-reviewed gold standard.

## Coverage

The original dataset has 20 scenario families with 50 cases each. It covers direct and
renamed copies, trimming, integer/decimal/boolean/date parsing, concatenation,
lookups, defaults, nullable values, ignored source fields, mixed plans, all
supported scalar types, target constraint violations, invalid scalar
quarantine, duplicate keys, target conflicts and blocking semantic questions.

The full-record dataset adds another 20 families with 50 cases each. Every case
converts a complete customer record and covers nested addresses, arrays, email
case normalization, date and boolean formats, thousands-separated decimals,
empty-to-null values, invalid nested inputs, duplicate keys and target conflicts.

## Generate and validate

Run from the repository root:

```bash
venv/bin/python -m evaluation.generate_gold_dataset
venv/bin/python -m evaluation.generate_full_record_gold_dataset
```

Generation validates executable schemas and mappings with the application
contracts and checks expected records through the deterministic transformation,
target-validation and dataset-key engines.

## Important evaluation rule

This dataset is evaluation-only. Do not use its cases for QLoRA training. Keep
it unchanged when comparing the baseline Qwen model with a QLoRA candidate;
create a separate training dataset so the evaluation does not leak into model
training.

## Run evaluation

Verify the complete evaluator locally without making AI API calls:

```bash
venv/bin/python -m evaluation.run_evaluation \
  --mode gold \
  --dataset all \
  --output-dir evaluation/results/gold-check
```

Evaluate a small configured-model sample first:

```bash
venv/bin/python -m evaluation.run_evaluation \
  --mode ai \
  --dataset all \
  --limit 10 \
  --concurrency 1 \
  --output-dir evaluation/results/qwen-sample
```

Add `--resume` to skip case IDs already present in `predictions.jsonl`. Generated
reports are ignored by Git and contain predictions, case scores and a summary.
The summary sets `official_gold_evaluation` to `false` while any selected label
is still pending human review, so candidate-dataset scores are not mistaken for
final model quality.

For a difficult full-record case, use `--dataset full --limit 1` and set
`--request-timeout-seconds 120 --max-retries 0`. The evaluator enforces a
request deadline and records provider, timeout, parsing and contract failures
in `predictions.jsonl`. `--structured-method json_mode` is a fallback for
providers that reject strict JSON schema, but it does not bypass validation.
