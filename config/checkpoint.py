from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from config.settings import get_settings


def checkpoint_database_url() -> str:
    return (
        get_settings()
        .database_url.get_secret_value()
        .replace("postgresql+psycopg://", "postgresql://", 1)
    )


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_database_url()
    ) as checkpointer:
        yield checkpointer
