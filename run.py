"""نقطه ورود حلی بات."""

from __future__ import annotations

import asyncio
import logging
import sys

from core.config import ConfigError, load_settings
from core.logging import setup_logging
from database.session import create_engine, create_session_factory, wait_for_database

logger = logging.getLogger("helli")


async def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"خطای تنظیمات: {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level)
    engine = create_engine(settings.database_url)
    try:
        await wait_for_database(engine)
        # import تنبل: فقط وقتی تنظیمات و دیتابیس درست بودند aiogram بارگذاری می‌شود.
        from platforms.telegram.app import run_telegram

        await run_telegram(settings, create_session_factory(engine))
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Stopped")
