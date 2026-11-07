"""درخواست‌های تأیید (مثل مسدودی دائمی) که منتظر دکمه مدیر هستند.

در حافظه نگه داشته می‌شوند: اگر ربات ری‌استارت شود، درخواست‌های تأییدنشده منقضی
می‌شوند و مدیر باید دستور را دوباره بفرستد. این رفتار امن‌تر از ذخیره‌کردن
درخواست‌های حساس در دیتابیس است.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

DEFAULT_TTL_SECONDS = 120.0
MAX_PENDING = 1_000


@dataclass(frozen=True, slots=True)
class PendingAction:
    token: str
    kind: str  # "ban"
    group_external_id: int
    actor_external_id: int
    target_external_id: int
    target_name: str
    reason: str | None
    created_at: float


class PendingConfirmations:
    def __init__(self, ttl: float = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._items: dict[str, PendingAction] = {}

    def create(
        self,
        *,
        kind: str,
        group_external_id: int,
        actor_external_id: int,
        target_external_id: int,
        target_name: str,
        reason: str | None,
    ) -> PendingAction:
        self._sweep()
        action = PendingAction(
            token=secrets.token_hex(4),
            kind=kind,
            group_external_id=group_external_id,
            actor_external_id=actor_external_id,
            target_external_id=target_external_id,
            target_name=target_name,
            reason=reason,
            created_at=time.monotonic(),
        )
        self._items[action.token] = action
        return action

    def peek(self, token: str) -> PendingAction | None:
        """درخواست را بدون حذف برمی‌گرداند؛ اگر منقضی شده باشد None."""
        action = self._items.get(token)
        if action is None:
            return None
        if time.monotonic() - action.created_at > self._ttl:
            self._items.pop(token, None)
            return None
        return action

    def discard(self, token: str) -> None:
        self._items.pop(token, None)

    def _sweep(self) -> None:
        now = time.monotonic()
        expired = [token for token, item in self._items.items() if now - item.created_at > self._ttl]
        for token in expired:
            self._items.pop(token, None)
        # سقف ساده برای جلوگیری از رشد حافظه در گروه‌های شلوغ.
        if len(self._items) > MAX_PENDING:
            self._items.clear()
