"""کمک‌کننده‌های امن برای تماس‌های رابط کاربری تلگرام.

هدف: هیچ خطای شبکه‌ای یا نبود دسترسی باعث نشود کاربر بلاتکلیف بماند
(دکمه شیشه‌ای در حالت لودینگ گیر کند یا پنل بدون پاسخ بماند).
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from platforms.telegram.resilience import with_retry

logger = logging.getLogger(__name__)


async def answer(
    callback: CallbackQuery, text: str | None = None, *, alert: bool = False
) -> None:
    """به دکمه شیشه‌ای پاسخ می‌دهد؛ خطا فقط لاگ می‌شود."""
    try:
        await with_retry(
            lambda: callback.answer(text, show_alert=alert), what="answer callback", attempts=2
        )
    except Exception as exc:
        logger.debug("Could not answer callback: %s", exc)


async def safe_send(message: Message | None, text: str, **kwargs: Any) -> bool:
    """پیام تازه می‌فرستد؛ در صورت شکست False برمی‌گرداند."""
    if message is None:
        return False
    try:
        await with_retry(lambda: message.answer(text, **kwargs), what="send message")
        return True
    except Exception as exc:
        logger.warning("Could not send message: %s", exc)
        return False


async def safe_edit(
    message: Message | None, text: str, *, fallback_send: bool = False, **kwargs: Any
) -> bool:
    """پیام را ویرایش می‌کند.

    - «message is not modified» خطا نیست (کاربر همان دکمه را دوباره زده).
    - در خطای گذرای شبکه چند بار تلاش می‌شود.
    - اگر ویرایش ممکن نشد و `fallback_send` روشن باشد، نسخه تازه می‌فرستد.
    """
    if message is None:
        return False
    try:
        await with_retry(lambda: message.edit_text(text, **kwargs), what="edit message")
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        logger.debug("Could not edit message: %s", exc)
    except Exception as exc:
        logger.warning("Could not edit message after retries: %s", exc)

    if fallback_send:
        return await safe_send(message, text, **kwargs)
    return False
