# SchemaBridge

SchemaBridge is an AI-assisted data migration workbench for one bounded JSON
dataset. Phase 1 provides immutable input snapshots, deterministic validation,
profiling, retry foundations, and audit history.

## Current scope

- One UTF-8 JSON source dataset containing a top-level array of objects.
- One source schema and one target schema per migration workspace.
- Maximum upload size: 20 MB.
- Maximum source records: 10,000.
- Empty datasets are rejected.
- Maximum fields per schema and record: 200.
- Nested objects and scalar arrays are accepted within configured size and
  depth limits.
- Supported types: string, integer, decimal, boolean, date, datetime, array,
  and object.
- Controlled rules support nested-path extraction, text case normalization,
  character removal, scalar-to-text conversion, string splitting, and
  empty-to-null conversion.
- Exactly one required, non-nullable, unique target business key.
- Source undeclared fields are preserved for profiling.
- Target undeclared fields are rejected.
- Arbitrary Python, JavaScript, SQL, and user-defined transformations are not supported.

## End-to-end Phase 1 flow

```text
Create project
→ submit source and target schemas
→ upload JSON records
→ validate limits and structure
→ preserve the original upload
→ create deterministic hashes
→ store an immutable dataset snapshot and source records
→ profile field types, missing values, lengths, and duplicates
→ preserve audit history
```

## Project structure

```text
SchemaBridge/
├── main.py
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
├── config/          # Settings, constants, and database sessions
├── contracts/       # Pydantic request and response validation
├── models/          # SQLAlchemy persistence models
├── repositories/    # Database queries and writes
├── services/        # JSON checks, upload, hashes, and data summary
├── routes/          # FastAPI endpoints and dependencies
├── middleware/      # Request IDs and consistent API errors
├── storage/         # Local immutable upload storage
├── database/        # Alembic migrations
└── deployment/      # Backend Dockerfile
```

## First-time setup

Run these commands from the repository root. Copy `.env.example` only when a
local `.env` file does not already exist.

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
npm --prefix frontend install
```

Set `SCHEMABRIDGE_AI_API_KEY` in `.env` before running the AI planner or an
AI-mode evaluation. Gold-pipeline verification does not require an AI key.

## Run the application locally

Start PostgreSQL and apply all migrations:

```bash
docker compose up -d postgres
venv/bin/alembic upgrade head
```

Start the backend in terminal 1:

```bash
venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in terminal 2:

```bash
npm --prefix frontend run dev
```

Open:

- frontend: `http://127.0.0.1:3000`;
- API documentation: `http://127.0.0.1:8000/docs`;
- health endpoint: `http://127.0.0.1:8000/health`.

Check the backend from a terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

## Run the complete Docker application

The API container does not apply migrations automatically. Start PostgreSQL,
run migrations once, and then start every service:

```bash
docker compose up -d postgres
docker compose run --rm api alembic upgrade head
docker compose up -d api frontend
docker compose ps
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

Inspect service logs when needed:

```bash
docker compose logs api
docker compose logs frontend
docker compose logs postgres
```

Stop the application without deleting database volumes:

```bash
docker compose down
```

## Validate the backend and database

When the backend uses the local virtual environment:

```bash
venv/bin/python -m py_compile config/*.py contracts/*.py services/*.py evaluation/*.py
venv/bin/python -c "import main; main.app.openapi(); print('backend and OpenAPI valid')"
venv/bin/alembic current
venv/bin/alembic check
```

Show PostgreSQL tables:

```bash
docker compose exec -T postgres \
  psql -U schemabridge -d schemabridge -c "\\dt"
```

## Validate the frontend

```bash
npm --prefix frontend run build
```

## Generate and validate both gold-candidate datasets

```bash
venv/bin/python -m evaluation.generate_gold_dataset
venv/bin/python -m evaluation.generate_full_record_gold_dataset
wc -l evaluation/gold_cases.jsonl evaluation/gold_full_record_cases.jsonl
```

The final command must show 1,000 lines in each file and 2,000 total.

## Test the complete evaluation pipeline locally

This command does not call the AI provider. It replays all expected proposals
through plan validation, deterministic transformation, target validation and
metric calculation:

```bash
venv/bin/python -m evaluation.run_evaluation \
  --mode gold \
  --dataset all \
  --output-dir evaluation/results/gold-check
```

Generated reports:

```text
evaluation/results/gold-check/
├── predictions.jsonl
├── case_scores.jsonl
└── summary.json
```

Inspect the overall result:

```bash
venv/bin/python -c "import json; print(json.dumps(json.load(open('evaluation/results/gold-check/summary.json'))['overall'], indent=2))"
```

## Evaluate the configured AI model

Run a small sample before starting a large evaluation because every case makes
an external model request:

```bash
venv/bin/python -m evaluation.run_evaluation \
  --mode ai \
  --dataset all \
  --limit 10 \
  --concurrency 1 \
  --output-dir evaluation/results/qwen-sample
```

Resume the same run without repeating completed case IDs:

```bash
venv/bin/python -m evaluation.run_evaluation \
  --mode ai \
  --dataset all \
  --limit 10 \
  --concurrency 1 \
  --output-dir evaluation/results/qwen-sample \
  --resume
```

The reports directory is ignored by Git. Evaluation summaries remain marked
`official_gold_evaluation: false` until every selected label is approved by a
human domain reviewer.

### If the hosted model fails on a full-record case

The current Qwen3-4B Hugging Face route has returned HTTP 500 for strict JSON
schema output and an invalid proposal in JSON mode on a complete customer
record. A Qwen3-32B trial returned a proposal with invalid dotted source field
names, and a follow-up trial reached the 120-second request limit. These are
model/provider results, not a successful full-record AI evaluation.

Start with one case and a bounded request:

```bash
venv/bin/python -m evaluation.run_evaluation \
  --mode ai --dataset full --limit 1 --concurrency 1 \
  --structured-method json_schema \
  --request-timeout-seconds 120 --max-retries 0 \
  --output-dir evaluation/results/full-one
```

Read `predictions.jsonl` for the exact error. `--structured-method json_mode`
is available when a provider does not support strict JSON schema, but its
output still has to pass the same Pydantic and deterministic plan checks. Set
`SCHEMABRIDGE_AI_MODEL` to a provider/model that supports the complete proposal
contract and rerun the same reviewed cases before making it the default.
