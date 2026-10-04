from enum import Enum


class SchemaRole(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class SupportedDataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class AdditionalFieldsPolicy(str, Enum):
    PROFILE = "profile"
    REJECT = "reject"


class DatasetStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BUNDLE_MISMATCH = "BUNDLE_MISMATCH"
    STALE_TARGET_REVISION = "STALE_TARGET_REVISION"
    ILLEGAL_STATE = "ILLEGAL_STATE"
    TARGET_KEY_CONFLICT = "TARGET_KEY_CONFLICT"
    ROLLBACK_CONFLICT = "ROLLBACK_CONFLICT"


SCHEMA_FORMAT_VERSION = "1.0"
CANONICALIZATION_VERSION = "1.0"
HASH_ALGORITHM = "sha256"
TRANSFORMATION_ENGINE_VERSION = "1.0"
APPROVAL_POLICY_VERSION = "1.0"
