# SchemaBridge Limits

## Dataset limits

- One source dataset per migration workspace
- JSON input only
- UTF-8 encoding
- Top-level array of objects
- Maximum upload size: 20 MB
- Maximum records: 10,000
- Maximum fields per record: 200
- Maximum record size: 256 KB
- Maximum string length: 100,000 characters
- Empty datasets are rejected
- Duplicate JSON keys are rejected
- NaN and infinity are rejected
- Inputs are never silently truncated

## Schema limits

- One source schema
- One target schema
- Maximum fields per schema: 200
- Flat records only
- Nested objects are unsupported
- Arrays inside records are unsupported
- Exactly one target business key
- Arbitrary validation code is unsupported

## Migration limits

- One source record produces zero or one target record
- Insert-only target operations
- Invalid records are quarantined
- Only registered transformation rules may execute
- No user-provided Python, JavaScript or SQL
- No live production database connectors