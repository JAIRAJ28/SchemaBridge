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
- Flat records only; nested objects and arrays are rejected.
- Supported types: string, integer, decimal, boolean, date, and datetime.
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

## Run locally

```bash
docker compose up -d postgres
venv/bin/alembic upgrade head
venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Check the API:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Database verification

```bash
venv/bin/alembic current
venv/bin/alembic check
```
