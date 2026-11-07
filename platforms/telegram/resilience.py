"""مقاوم‌سازی تماس‌های تلگرام در برابر خطاهای گذرای شبکه.

خطاهایی مثل `ServerDisconnectedError` یا `TimeoutError` معمولاً یعنی اتصال
keep-alive قدیمی شده یا شبکه یک لحظه قطع شده است؛ یک تلاش دوباره با اتصال تازه
تقریباً همیشه جواب می‌دهد. بدون این لایه، یک قطعی کوتاه باعث می‌شود پنل آپدیت
نشود و دکمه شیشه‌ای برای کاربر در حالت لودینگ بماند.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import aiohttp
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# خطاهایی که با تلاش دوباره ممکن است حل شوند.
TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    TelegramNetworkError,
)

DEFAULT_ATTEMPTS = 3
BASE_DELAY = 0.4
MAX_DELAY = 3.0


def is_transient(exc: BaseException) -> bool:
    """آیا خطا موقتی است (شبکه/محدودیت نرخ/خطای سرور)؟"""
    return isinstance(exc, (*TRANSIENT_ERRORS, TelegramRetryAfter, TelegramServerError))


async def with_retry(
    call: Callable[[], Awaitable[T]],
    *,
    what: str = "telegram call",
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
) -> T:
    """`call` را اجرا می‌کند و در صورت خطای گذرا با تأخیر فزاینده دوباره تلاش می‌کند.

    `call` باید یک تابع بدون آرگومان باشد که هر بار یک coroutine تازه می‌سازد
    (coroutine یک بار قابل انتظار است و دوباره اجرا نمی‌شود).
    """
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except TelegramRetryAfter as exc:
            # تلگرام خودش گفته چند ثانیه صبر کنیم.
            if attempt >= attempts:
                raise
            delay = min(max_delay, max(0.5, float(exc.retry_after)))
            logger.warning("%s: rate limited, retrying in %.1fs", what, delay)
            await asyncio.sleep(delay)
        except TRANSIENT_ERRORS as exc:
            if attempt >= attempts:
                raise
            delay = min(max_delay, base_delay * 2 ** (attempt - 1))
            logger.warning(
                "%s failed (%s/%s): %s — retrying in %.1fs",
                what,
                attempt,
                attempts,
                exc.__class__.__name__,
                delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(f"{what}: retry loop finished without result")
