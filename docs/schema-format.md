# SchemaBridge Schema Format

## Supported field types

- string
- integer
- decimal
- boolean
- date
- datetime

## Source schema behavior

The source schema uses:

additional_fields_policy = profile

Undeclared source fields are preserved and reported.

## Target schema behavior

The target schema uses:

additional_fields_policy = reject

Transformed records cannot contain undeclared target fields.

## Missing and null

Missing means that a property does not exist.

Null means that the property exists with a JSON null value.

Empty strings, whitespace strings, zero and false are not treated
as missing.

## Target business key

The target schema must have exactly one business key.

The business-key field must:

- Exist in target fields
- Be required
- Be non-nullable
- Be unique

## Immutability

An accepted schema cannot be edited.

Any correction creates a new schema snapshot and version.