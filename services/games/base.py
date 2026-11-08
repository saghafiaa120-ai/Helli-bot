"""زیرساخت مشترک بازی‌ها.

بازی‌ها در حافظه نگه داشته می‌شوند (مثل درخواست‌های تأیید مسدودی)؛ چون هر بازی
چند دقیقه عمر دارد و با ری‌استارت ربات از بین رفتنش مشکل جدی نیست. منطق بازی
کاملاً مستقل از تلگرام است تا بدون aiogram هم تست شود.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class GameError(Exception):
    """خطای قابل نمایش در بازی؛ `kind` نوع پیام مناسب را مشخص می‌کند."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(slots=True)
class GamePlayer:
    """یک بازیکن در بازی (شناسه تلگرام، نام نمایشی، نقش و زنده‌بودن)."""

    user_id: int
    name: str
    role: str | None = None
    alive: bool = True


class Game(Protocol):
    """قرارداد مشترک بازی‌ها (فقط چیزهایی که ثبت‌کننده بازی لازم دارد)."""

    kind: str
    host_id: int

    def has_player(self, user_id: int) -> bool: ...

    def is_finished(self) -> bool: ...


class GameRegistry:
    """بازی‌های فعال؛ برای هر گفتگو حداکثر یک بازی.

    بازی‌های خصوصی (نقش‌ها و انتخاب‌های شب) با شناسه گفتگوی گروه ثبت می‌شوند،
    ولی دکمه‌های پیام خصوصی با شناسه بازیکن پیدا می‌شوند (`find_for_player`).
    """

    def __init__(self) -> None:
        self._by_chat: dict[int, Game] = {}

    def get(self, chat_id: int) -> Game | None:
        return self._by_chat.get(chat_id)

    def set(self, chat_id: int, game: Game) -> None:
        self._by_chat[chat_id] = game

    def drop(self, chat_id: int, game: Game | None = None) -> None:
        """بازی را حذف می‌کند؛ اگر `game` بدهید فقط وقتی همان بازی فعال باشد."""
        current = self._by_chat.get(chat_id)
        if game is None or current is game:
            self._by_chat.pop(chat_id, None)

    def find_for_player(self, user_id: int) -> Game | None:
        """بازی فعالی که این کاربر در آن بازیکن است (برای دکمه‌های پیام خصوصی)."""
        for game in self._by_chat.values():
            if game.has_player(user_id):
                return game
        return None

    def clear(self) -> None:
        self._by_chat.clear()

    def __len__(self) -> int:
        return len(self._by_chat)

    def items(self) -> Any:
        return self._by_chat.items()
