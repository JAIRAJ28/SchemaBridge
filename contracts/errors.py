from typing import Any

from pydantic import Field

from config.constants import ErrorCode
from contracts.common import StrictContract


class ErrorDetail(StrictContract):
    field: str | None = None
    location: list[str | int] = Field(default_factory=list)
    information: dict[str, Any] = Field(default_factory=dict)


class APIErrorResponse(StrictContract):
    error_code: ErrorCode
    message: str
    request_id: str
    retryable: bool = False
    details: list[ErrorDetail] = Field(default_factory=list)
