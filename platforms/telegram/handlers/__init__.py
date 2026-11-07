from aiogram import Router

from platforms.telegram.handlers import (
    group_events,
    help,
    moderation,
    panel,
    start,
    stats,
)


def get_routers() -> list[Router]:
    """روترهای تازه برای هر Dispatcher.

    روتر aiogram فقط یک بار به یک Dispatcher قابل اتصال است؛ به همین دلیل هر
    ماژول `build_router()` دارد و روتر ماژولی سراسری نداریم.
    ترتیب مهم است: دستورها قبل از رویدادهای عمومی بررسی می‌شوند.
    """
    return [
        start.build_router(),
        help.build_router(),
        panel.build_router(),
        moderation.build_router(),
        stats.build_router(),
        group_events.build_router(),
    ]
