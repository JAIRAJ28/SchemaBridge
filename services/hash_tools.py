from hashlib import sha256
from typing import Any

from services.json_format import canonical_json_bytes


def calculate_bytes_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def calculate_canonical_hash(value: Any) -> str:
    return calculate_bytes_hash(canonical_json_bytes(value))
