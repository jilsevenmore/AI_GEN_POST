from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis import asyncio as aioredis
from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter()
settings = get_settings()


@router.get("/db", tags=["Health"])
async def db_health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception as e:
        return {"database": "disconnected", "error": str(e)}


@router.get("/redis", tags=["Health"])
async def redis_health():
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        await redis.ping()
        await redis.close()
        return {"redis": "connected"}
    except Exception as e:
        return {"redis": "disconnected", "error": str(e)}


@router.get("/all", tags=["Health"])
async def all_health(db: AsyncSession = Depends(get_db)):
    db_status = await db_health(db)
    redis_status = await redis_health()
    return {
        "database": db_status,
        "redis": redis_status,
        "overall": "healthy" if db_status["database"] == "connected" and redis_status["redis"] == "connected" else "degraded",
    }