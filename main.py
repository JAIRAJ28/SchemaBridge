from fastapi import FastAPI

from config.settings import get_settings
from middleware.exception_handler import (
    register_exception_handlers,
)
from middleware.request_context import (
    request_context_middleware,
)

settings = get_settings()


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
    )

    application.middleware("http")(request_context_middleware)

    register_exception_handlers(application)

    return application


app = create_application()
