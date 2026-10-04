# SchemaBridge
MapSure is an AI-assisted data migration workbench for schema mapping, versioned migration plans, and deterministic validation. It supports human-approved execution into a mock target, invalid-record quarantine, duplicate-safe retries, source-to-target reconciliation, rollback, and audit history.

## Current product scope

- One UTF-8 JSON source dataset containing a top-level array of objects.
- One source schema and one target schema per migration workspace.
- Maximum uncompressed upload size: 20 MB.
- Maximum source records: 10,000.
- Maximum fields per schema and record: 200.
- Flat records only; nested objects and arrays are not supported.
- Supported types: string, integer, decimal, boolean, date, and datetime.
- Exactly one required, non-nullable, unique target business key.
- Source undeclared fields are preserved for profiling; target undeclared fields are rejected.
- Inputs above the configured limits are rejected without truncation.
- Arbitrary Python, JavaScript, SQL, and user-defined transformations are not supported.



SchemaBridge/
├── main.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── database.py
│   ├── logging.py
│   ├── security.py
│   └── constants.py
│
├── routes/
│   ├── __init__.py
│   ├── dependencies.py
│   ├── health_routes.py
│   ├── project_routes.py
│   ├── dataset_routes.py
│   ├── schema_routes.py
│   └── profile_routes.py
│
├── controller/
│   ├── __init__.py
│   ├── project_controller.py
│   ├── dataset_controller.py
│   ├── schema_controller.py
│   └── profile_controller.py
│
├── contracts/
│   ├── __init__.py
│   ├── common.py
│   ├── project.py
│   ├── schema_definition.py
│   ├── dataset.py
│   ├── profile.py
│   ├── audit.py
│   └── errors.py
│
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── project.py
│   ├── schema_snapshot.py
│   ├── dataset_snapshot.py
│   ├── source_record.py
│   ├── dataset_profile.py
│   ├── idempotency_record.py
│   └── audit_event.py
│
├── repositories/
│   ├── __init__.py
│   ├── project_repository.py
│   ├── schema_repository.py
│   ├── dataset_repository.py
│   ├── profile_repository.py
│   ├── idempotency_repository.py
│   └── audit_repository.py
│
├── services/
│   ├── __init__.py
│   ├── project_service.py
│   ├── schema_service.py
│   ├── dataset_ingestion_service.py
│   ├── json_validation_service.py
│   ├── canonicalization_service.py
│   ├── fingerprint_service.py
│   ├── profiling_service.py
│   ├── storage_service.py
│   ├── idempotency_service.py
│   └── audit_service.py
│
├── middleware/
│   ├── __init__.py
│   ├── request_context.py
│   ├── exception_handler.py
│   ├── request_logging.py
│   └── security_headers.py
│
├── storage/
│   ├── __init__.py
│   ├── base.py
│   ├── local_storage.py
│   └── s3_storage.py
│
├── database/
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_phase_one_foundation.py
│   └── seed/
│       └── README.md
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
│
├── docs/
│   ├── architecture.md
│   ├── api-contracts.md
│   ├── schema-format.md
│   ├── limits.md
│   ├── data-retention.md
│   └── phase-1-checklist.md
│
└── deployment/
    ├── backend.Dockerfile
    ├── docker-compose.yml
    └── healthcheck.sh
