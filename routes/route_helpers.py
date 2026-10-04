from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from config.database import get_database_session
from config.settings import get_settings
from contracts.page import PaginationParams
from contracts.errors import ErrorDetail
from middleware.error_handler import ApplicationError
from services.auth_actions import decode_access_token


DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


bearer_scheme = HTTPBearer(auto_error=False)


def get_actor_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> str:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise ApplicationError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="A bearer access token is required.",
            status_code=401,
        )
    return decode_access_token(credentials.credentials)


ActorId = Annotated[
    str,
    Depends(get_actor_id),
]


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
