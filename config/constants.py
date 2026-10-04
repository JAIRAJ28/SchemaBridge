# Maximum_upload: 20
from enum import Enum

class SchemaRole(str,Enum):
    SOURCE='source'
    TARGET='target'

class SupportedDataType(str,Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"

class AdditionalFieldsPolicy(str,Enum):
    PROFILE='profile'
    REJECT='reject'

class DatasetStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


SCHEMA_FORMAT_VERSION = "1.0"
CANONICALIZATION_VERSION = "1.0"
HASH_ALGORITHM = "sha256"

