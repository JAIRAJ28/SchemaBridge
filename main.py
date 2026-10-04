from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import (
    check_database_connection,
    close_database_connection,
)
from config.checkpoint import open_checkpointer
from config.settings import get_settings
from middleware.error_handler import (
    register_exception_handlers,
)
from middleware.request_id import (
    request_context_middleware,
)
from routes.dataset_routes import router as dataset_router
from routes.dry_run_routes import router as dry_run_router
from routes.health_routes import router as health_router
from routes.data_summary_routes import router as profile_router
from routes.project_routes import router as project_router
from routes.plan_routes import router as plan_router
from routes.schema_routes import router as schema_router
from routes.agent_routes import router as agent_router
from routes.approval_routes import router as approval_router
from routes.migration_routes import router as migration_router
from routes.auth_routes import router as auth_router

settings = get_settings()


@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    await check_database_connection()
    try:
        async with open_checkpointer() as checkpointer:
            await checkpointer.setup()
            application.state.checkpointer = checkpointer
            yield
    finally:
        await close_database_connection()


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    application.middleware("http")(request_context_middleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "Idempotency-Key",
        ],
    )

    register_exception_handlers(application)

    application.include_router(health_router)
    application.include_router(auth_router, prefix=settings.api_prefix)
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
    application.include_router(
        plan_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        dry_run_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        agent_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        approval_router,
        prefix=settings.api_prefix,
    )
    application.include_router(
        migration_router,
        prefix=settings.api_prefix,
    )

    return application


app = create_application()
