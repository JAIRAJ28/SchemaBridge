import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from config.constants import ErrorCode
from contracts.errors import APIErrorResponse, ErrorDetail

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int,
        retryable: bool = False,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or []


def get_request_id(request: Request) -> str:
    return getattr(
        request.state,
        "request_id",
        "unknown",
    )


def create_error_response(
    *,
    request: Request,
    status_code: int,
    error_code: ErrorCode,
    message: str,
    retryable: bool = False,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    error = APIErrorResponse(
        error_code=error_code,
        message=message,
        request_id=get_request_id(request),
        retryable=retryable,
        details=details or [],
    )

    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(mode="json"),
    )


async def application_error_handler(
    request: Request,
    exception: ApplicationError,
) -> JSONResponse:
    return create_error_response(
        request=request,
        status_code=exception.status_code,
        error_code=exception.error_code,
        message=exception.message,
        retryable=exception.retryable,
        details=exception.details,
    )


async def request_validation_error_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    details: list[ErrorDetail] = []

    for error in exception.errors():
        location = list(error.get("loc", []))

        field = None
        if location:
            field = str(location[-1])

        details.append(
            ErrorDetail(
                field=field,
                location=location,
                information={
                    "reason": error.get(
                        "msg",
                        "Invalid value.",
                    )
                },
            )
        )

    return create_error_response(
        request=request,
        status_code=422,
        error_code=ErrorCode.VALIDATION_ERROR,
        message="The submitted request is invalid.",
        retryable=False,
        details=details,
    )


def error_code_for_http_status(
    status_code: int,
) -> ErrorCode:
    mapping = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        405: ErrorCode.METHOD_NOT_ALLOWED,
        409: ErrorCode.CONFLICT,
    }

    return mapping.get(
        status_code,
        ErrorCode.BAD_REQUEST,
    )


async def http_exception_handler(
    request: Request,
    exception: HTTPException,
) -> JSONResponse:
    if isinstance(exception.detail, str):
        message = exception.detail
    else:
        message = "The request could not be completed."

    return create_error_response(
        request=request,
        status_code=exception.status_code,
        error_code=error_code_for_http_status(exception.status_code),
        message=message,
        retryable=False,
    )


async def unexpected_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled request exception type: %s",
        type(exception).__name__,
        extra={
            "request_id": get_request_id(request),
            "method": request.method,
            "path": request.url.path,
        },
    )

    return create_error_response(
        request=request,
        status_code=500,
        error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        message="An unexpected server error occurred.",
        retryable=False,
    )


def register_exception_handlers(
    application: FastAPI,
) -> None:
    application.add_exception_handler(
        ApplicationError,
        application_error_handler,
    )

    application.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )

    application.add_exception_handler(
        HTTPException,
        http_exception_handler,
    )

    application.add_exception_handler(
        Exception,
        unexpected_exception_handler,
    )
