import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    content = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return content.encode("utf-8")
