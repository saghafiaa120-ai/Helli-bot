"""فیلتر دستور: اسلش‌دار (`/ban`) و معادل فارسی بدون اسلش («مسدود»)."""

from __future__ import annotations

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message

from domain.commands import ParsedCommand, parse_command


class TextCommand(BaseFilter):
    """پیام متنی را به دستور تبدیل می‌کند و نتیجه را در `parsed` می‌گذارد.

    معادل فارسی بدون اسلش فقط وقتی دستور حساب می‌شود که پیام Reply باشد، یا
    دقیقاً همان یک کلمه باشد، یا هدف/مدت همراه داشته باشد؛ این‌طوری جمله‌های
    معمولی مثل «سکوت کن» به‌اشتباه دستور تلقی نمی‌شوند.
    """

    def __init__(self, *commands: str) -> None:
        self._commands = frozenset(commands)

    async def __call__(self, message: Message) -> dict[str, Any] | bool:
        text = message.text
        if not text:
            return False
        parsed = parse_command(text)
        if parsed is None or parsed.name not in self._commands:
            return False
        if parsed.is_alias and not self._alias_allowed(message, parsed):
            return False
        return {"parsed": parsed}

    @staticmethod
    def _alias_allowed(message: Message, parsed: ParsedCommand) -> bool:
        if message.reply_to_message is not None:
            return True
        if parsed.args.target or parsed.args.duration_given:
            return True
        # «اطلاعات» تنها: دستور است و راهنما نشان داده می‌شود.
        return parsed.args.reason is None
