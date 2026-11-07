"""موتور و نشست‌های دیتابیس (ناهمگام) برای ربات."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


def create_engine(database_url: str) -> AsyncEngine:
    # pool_recycle: جلوگیری از بسته شدن اتصال‌های بیکار توسط MySQL (wait_timeout).
    return create_async_engine(database_url, pool_pre_ping=True, pool_recycle=3600)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def wait_for_database(engine: AsyncEngine, attempts: int = 30, delay: float = 2.0) -> None:
    """تا آماده شدن دیتابیس چند بار تلاش می‌کند.

    اگر MySQL (XAMPP) دیرتر از ربات روشن شود، به‌جای خطای فوری چند ثانیه صبر می‌کند.
    """
    for attempt in range(1, attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection OK")
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            logger.warning("Database not ready (%s/%s): %s", attempt, attempts, exc)
            await asyncio.sleep(delay)
