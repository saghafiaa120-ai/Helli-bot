"""راهنمای ربات.

راهنما به بخش‌های کوتاه شکسته شده و با دکمه جابه‌جا می‌شود؛ این‌طوری کاربر با یک
دیوار متن روبه‌رو نمی‌شود و هر بخش را جدا می‌بیند.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from core import texts_fa
from platforms.telegram import ui
from platforms.telegram.help_keyboards import help_keyboard
from platforms.telegram.resilience import with_retry

logger = logging.getLogger(__name__)


async def cmd_help(message: Message) -> None:
    await message.answer(texts_fa.help_text(), reply_markup=help_keyboard("main"))


async def on_help_callback(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    section = parts[1] if len(parts) > 1 else "main"

    if section == "close":
        await _close(callback)
        return

    try:
        await ui.safe_edit(
            callback.message,
            texts_fa.help_section(section),
            reply_markup=help_keyboard(section),
            fallback_send=True,
        )
    finally:
        await ui.answer(callback)


async def _close(callback: CallbackQuery) -> None:
    message = callback.message
    if message is not None:
        try:
            await with_retry(lambda: message.delete(), what="help delete")
        except Exception:
            await ui.safe_edit(message, texts_fa.help_closed())
    await ui.answer(callback)


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="help")
    router.message.register(cmd_help, Command("help"))
    router.callback_query.register(on_help_callback, F.data.startswith("help:"))
    return router
