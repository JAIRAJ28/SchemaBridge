from typing import Any
from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    field: str | None = None
    location: str | None = None
    information: dict[str, Any] = Field(default_factory=dict)

class APIErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
    retryable: bool = False
    details: list[ErrorDetail] = Field(default_factory=list)