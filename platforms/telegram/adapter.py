"""پیاده‌سازی PlatformAdapter برای تلگرام (تنها جایی که با Bot API تماس می‌گیرد)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import ChatPermissions

from domain.dto import AdminInfo, BotStatus, ChatRef
from platforms.base import Capabilities, PlatformAdapter, PlatformError
from platforms.telegram.mapping import PLATFORM, admin_info_from, bot_status_from, status_value
from platforms.telegram.resilience import TRANSIENT_ERRORS, with_retry

if TYPE_CHECKING:
    from aiogram import Bot

T = TypeVar("T")

# همه انواع «ارسال» که با سکوت بسته می‌شوند.
_SEND_FIELDS = (
    "can_send_messages",
    "can_send_audios",
    "can_send_documents",
    "can_send_photos",
    "can_send_videos",
    "can_send_video_notes",
    "can_send_voice_notes",
    "can_send_polls",
    "can_send_other_messages",
    "can_add_web_page_previews",
)
_OTHER_FIELDS = ("can_change_info", "can_invite_users", "can_pin_messages", "can_manage_topics")


def _classify(exc: TelegramAPIError) -> str:
    """دسته‌بندی خطای تلگرام برای نمایش پیام مناسب به کاربر."""
    if isinstance(exc, TelegramRetryAfter):
        return "rate_limited"
    if isinstance(exc, TelegramServerError):
        return "network"
    text = str(exc).lower()
    if "not enough rights" in text or "chat_admin_required" in text or "need to be administrator" in text:
        return "no_rights"
    if "user is an administrator" in text or "can't remove chat owner" in text or "can't restrict self" in text:
        return "target_is_admin"
    if "only for supergroups" in text or "only available for supergroups" in text:
        return "not_supergroup"
    if "user not found" in text or "participant_id_invalid" in text or "user_not_participant" in text:
        return "not_found"
    return "other"


def _wrap(exc: TelegramAPIError, method: str) -> PlatformError:
    return PlatformError(f"{method} failed: {exc}", kind=_classify(exc))


def _timestamp(until: datetime | None) -> int | None:
    """زمان UTC بدون tzinfo را به timestamp یونیکس تبدیل می‌کند.

    (aiogram اگر datetime بدون tzinfo بگیرد آن را «وقت محلی سرور» فرض می‌کند، پس int می‌دهیم.)
    """
    if until is None:
        return None
    return int(until.replace(tzinfo=UTC).timestamp())


class TelegramAdapter(PlatformAdapter):
    platform = PLATFORM
    capabilities = Capabilities(
        can_restrict_members=True, can_delete_messages=True, supports_buttons=True
    )

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @property
    def bot_user_id(self) -> int:
        return self._bot.id

    async def _call(self, method: str, call: Callable[[], Awaitable[T]]) -> T:
        """تماس با Bot API با تلاش دوباره در خطاهای گذرا و تبدیل به PlatformError."""
        try:
            return await with_retry(call, what=method)
        except TelegramRetryAfter as exc:
            raise _wrap(exc, method) from exc
        except TRANSIENT_ERRORS as exc:
            raise PlatformError(f"{method} network failure: {exc}", kind="network") from exc
        except TelegramAPIError as exc:
            raise _wrap(exc, method) from exc

    async def get_admins(self, chat: ChatRef) -> list[AdminInfo]:
        members = await self._call(
            "getChatAdministrators",
            lambda: self._bot.get_chat_administrators(chat.external_id),
        )
        infos = (admin_info_from(member) for member in members)
        return [info for info in infos if info is not None]

    async def get_bot_status(self, chat: ChatRef) -> BotStatus:
        member = await self._call(
            "getChatMember", lambda: self._bot.get_chat_member(chat.external_id, self._bot.id)
        )
        return bot_status_from(member)

    async def get_member_count(self, chat: ChatRef) -> int:
        return await self._call(
            "getChatMemberCount", lambda: self._bot.get_chat_member_count(chat.external_id)
        )

    async def send_text(self, chat: ChatRef, text: str) -> None:
        await self._call("sendMessage", lambda: self._bot.send_message(chat.external_id, text))

    # ----- مدیریت کاربران ------------------------------------------------------

    async def ban_member(self, chat: ChatRef, user_id: int, until: datetime | None) -> None:
        await self._call(
            "banChatMember",
            lambda: self._bot.ban_chat_member(
                chat.external_id, user_id, until_date=_timestamp(until), revoke_messages=False
            ),
        )

    async def unban_member(self, chat: ChatRef, user_id: int) -> bool:
        try:
            status = await self._member_status(chat, user_id)
        except PlatformError as exc:
            if exc.kind == "not_found":
                return False
            raise
        if status != "kicked":
            return False
        await self._call(
            "unbanChatMember",
            lambda: self._bot.unban_chat_member(chat.external_id, user_id, only_if_banned=True),
        )
        return True

    async def mute_member(self, chat: ChatRef, user_id: int, until: datetime | None) -> None:
        permissions = ChatPermissions(**{f: False for f in _SEND_FIELDS + _OTHER_FIELDS})
        await self._call(
            "restrictChatMember",
            lambda: self._bot.restrict_chat_member(
                chat.external_id,
                user_id,
                permissions=permissions,
                until_date=_timestamp(until),
                use_independent_chat_permissions=True,
            ),
        )

    async def unmute_member(self, chat: ChatRef, user_id: int) -> bool:
        try:
            status = await self._member_status(chat, user_id)
        except PlatformError as exc:
            if exc.kind == "not_found":
                return False
            raise
        if status != "restricted":
            return False

        # دسترسی‌ها به «پیش‌فرض خود گروه» برمی‌گردد، نه یک مقدار دلخواه ما.
        info = await self._call("getChat", lambda: self._bot.get_chat(chat.external_id))
        permissions = getattr(info, "permissions", None)
        if permissions is None:
            permissions = ChatPermissions(**{f: True for f in _SEND_FIELDS}, can_invite_users=True)
        await self._call(
            "restrictChatMember",
            lambda: self._bot.restrict_chat_member(
                chat.external_id,
                user_id,
                permissions=permissions,
                use_independent_chat_permissions=True,
            ),
        )
        return True

    async def kick_member(self, chat: ChatRef, user_id: int) -> None:
        """اخراج = مسدود کردن و بلافاصله رفع مسدودی (کاربر می‌تواند دوباره عضو شود)."""
        await self._call(
            "banChatMember",
            lambda: self._bot.ban_chat_member(chat.external_id, user_id, revoke_messages=False),
        )
        await self._call(
            "unbanChatMember",
            lambda: self._bot.unban_chat_member(chat.external_id, user_id, only_if_banned=True),
        )

    async def _member_status(self, chat: ChatRef, user_id: int) -> str:
        member = await self._call(
            "getChatMember", lambda: self._bot.get_chat_member(chat.external_id, user_id)
        )
        return status_value(member)
