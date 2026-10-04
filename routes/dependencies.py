from typing import Annotated

from fastapi import Query, Request

from config.constants import ErrorCode
from config.settings import get_settings
from contracts.common import PaginationParams
from contracts.errors import ErrorDetail
from middleware.exception_handler import ApplicationError


def get_request_id(request: Request) -> str:
    return request.state.request_id


async def get_pagination(
    page: Annotated[
        int,
        Query(ge=1),
    ] = 1,
    page_size: Annotated[
        int | None,
        Query(ge=1),
    ] = None,
) -> PaginationParams:
    settings = get_settings()

    selected_page_size = (
        page_size if page_size is not None else settings.default_page_size
    )

    if selected_page_size > settings.max_page_size:
        raise ApplicationError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="The requested page size is too large.",
            status_code=422,
            details=[
                ErrorDetail(
                    field="page_size",
                    location=["query", "page_size"],
                    information={"maximum": settings.max_page_size},
                )
            ],
        )

    return PaginationParams(
        page=page,
        page_size=selected_page_size,
    )
