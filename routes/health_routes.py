from fastapi import APIRouter

from config.database import check_database_connection


router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    await check_database_connection()
    return {"status": "healthy"}
