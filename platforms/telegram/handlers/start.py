from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from core import texts_fa


async def cmd_start(message: Message) -> None:
    """معرفی ربات؛ متن گفتگوی خصوصی با متن گروه فرق دارد."""
    if message.chat.type == "private":
        await message.answer(texts_fa.start_private())
    else:
        await message.answer(texts_fa.start_group())


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="start")
    router.message.register(cmd_start, CommandStart())
    return router
