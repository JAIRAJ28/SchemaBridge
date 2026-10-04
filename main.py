from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.database import (
    check_database_connection,
    close_database_connection,
)
from config.settings import get_settings
from middleware.error_handler import (
    register_exception_handlers,
)
from middleware.request_id import (
    request_context_middleware,
)
from routes.dataset_routes import router as dataset_router
from routes.health_routes import router as health_router
from routes.data_summary_routes import router as profile_router
from routes.project_routes import router as project_router
from routes.schema_routes import router as schema_router

settings = get_settings()


@asynccontextmanager
async def lifespan(
    _application: FastAPI,
) -> AsyncIterator[None]:
    await check_database_connection()

    yield

    await close_database_connection()


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    application.middleware("http")(request_context_middleware)

    register_exception_handlers(application)

    application.include_router(health_router)
    application.include_router(
        project_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        schema_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        dataset_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        profile_router,
        prefix=settings.api_prefix,
    )

    return application


app = create_application()
