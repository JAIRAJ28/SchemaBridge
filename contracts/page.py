from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from config.settings import get_settings


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaginationParams(StrictContract):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)

    @model_validator(mode="after")
    def validate_page_size(self) -> "PaginationParams":
        maximum = get_settings().max_page_size

        if self.page_size > maximum:
            raise ValueError(f"page_size cannot be greater than {maximum}.")

        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PageMetadata(StrictContract):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


ResponseItem = TypeVar("ResponseItem")


class PaginatedResponse(
    StrictContract,
    Generic[ResponseItem],
):
    items: list[ResponseItem]
    pagination: PageMetadata
    request_id: str
