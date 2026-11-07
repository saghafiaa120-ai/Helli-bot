from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from core.jalali import TEHRAN
from platforms.telegram.mapping import (
    GROUP_CHAT_TYPES,
    PLATFORM,
    chat_ref_from,
    enum_value,
    user_ref_from,
)
from platforms.telegram.onboarding import refresh_group
from services.group_service import GroupService
from services.membership_service import MembershipService
from services.message_counter import MessageCounter
from services.user_service import UserService

logger = logging.getLogger(__name__)

_MAX_CACHE_ENTRIES = 50_000

# فقط پیام‌های واقعی کاربران شمرده می‌شوند؛ پیام‌های خدماتی (ورود، خروج، سنجاق و ...) نه.
COUNTED_CONTENT_TYPES = frozenset(
    {
        "text", "photo", "video", "audio", "document", "voice", "video_note", "sticker",
        "animation", "poll", "contact", "location", "venue", "dice", "game",
    }
)


class TrackingMiddleware(BaseMiddleware):
    """گروه، کاربر و آخرین فعالیت او را از پیام‌های گروه ثبت می‌کند.

    همچنین تعداد پیام‌های هر کاربر را می‌شمارد (فقط عدد، نه متن).
    برای جلوگیری از نوشتن در دیتابیس به ازای هر پیام، اگر اطلاعات یک کاربر در یک
    گروه تغییری نکرده باشد، فقط هر `ttl` ثانیه یک بار ثبت می‌شود.
    خطای ثبت نباید پردازش خود پیام را متوقف کند.
    """

    def __init__(self, counter: MessageCounter, ttl: float = 300.0) -> None:
        self._counter = counter
        self._ttl = ttl
        self._seen: dict[tuple[int, int], tuple[float, int]] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        self._count(event)
        try:
            await self._track(event, data)
        except Exception:
            logger.exception("Activity tracking failed")
            session = data.get("session")
            if session is not None:
                await session.rollback()
        return await handler(event, data)

    def _count(self, event: Message) -> None:
        """هر پیام واقعی را در شمارنده درحافظه می‌شمارد (بدون دسترسی به دیتابیس)."""
        chat, user = event.chat, event.from_user
        if chat.type not in GROUP_CHAT_TYPES or user is None or user.is_bot:
            return
        if enum_value(event.content_type) not in COUNTED_CONTENT_TYPES:
            return
        # روز به وقت تهران و بر اساس زمان خود پیام (نه زمان پردازش آن) تعیین می‌شود.
        day = event.date.astimezone(TEHRAN).date()
        self._counter.add(PLATFORM, chat.id, user.id, day)

    async def _track(self, event: Message, data: dict[str, Any]) -> None:
        chat, user = event.chat, event.from_user
        if chat.type not in GROUP_CHAT_TYPES or user is None or user.is_bot:
            return
        # پیام خدماتی انتقال گروه: گروه قدیمی دیگر قابل استفاده نیست.
        if event.migrate_to_chat_id or event.migrate_from_chat_id:
            return

        fingerprint = hash(
            (
                user.username,
                user.first_name,
                user.last_name,
                user.language_code,
                chat.title,
                chat.username,
            )
        )
        key = (chat.id, user.id)
        now = time.monotonic()
        cached = self._seen.get(key)
        if cached is not None and cached[1] == fingerprint and now - cached[0] < self._ttl:
            return

        session = data["session"]
        adapter = data["adapter"]
        chat_ref = chat_ref_from(chat)

        group, created = await GroupService(session).ensure(chat_ref)
        if created:
            await refresh_group(session, adapter, group, chat_ref, refresh_bot_status=True)
        user_row = await UserService(session).upsert(user_ref_from(user))
        await MembershipService(session).touch_activity(group.id, user_row.id)

        if len(self._seen) >= _MAX_CACHE_ENTRIES:
            self._seen.clear()
        self._seen[key] = (now, fingerprint)
