"""رویدادهای مربوط به گروه: افزوده/حذف شدن ربات، تغییر اعضا و مدیران، انتقال گروه."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core import texts_fa
from core.enums import MemberStatus
from platforms.base import PlatformAdapter, PlatformError
from platforms.telegram.mapping import (
    GROUP_CHAT_TYPES,
    PLATFORM,
    bot_status_from,
    chat_ref_from,
    member_status_from,
    status_value,
    user_ref_from,
)
from platforms.telegram.onboarding import refresh_group
from services.group_service import GroupService
from services.membership_service import MembershipService
from services.moderation_service import ModerationService
from services.user_service import UserService

logger = logging.getLogger(__name__)

_ADMIN_STATUSES = {"administrator", "creator"}


async def on_bot_status_changed(
    event: ChatMemberUpdated, session: AsyncSession, adapter: PlatformAdapter
) -> None:
    """ربات به گروه اضافه شد، از آن خارج شد، یا دسترسی‌هایش عوض شد."""
    chat = chat_ref_from(event.chat)
    groups = GroupService(session)

    actor_id = None
    if event.from_user is not None:
        actor_id = (await UserService(session).upsert(user_ref_from(event.from_user))).id

    if status_value(event.new_chat_member) in ("left", "kicked"):
        await groups.mark_bot_removed(chat, actor_user_id=actor_id)
        return

    bot_status = bot_status_from(event.new_chat_member)
    group, joined = await groups.register(chat, bot_status, actor_user_id=actor_id)
    await refresh_group(session, adapter, group, chat)

    if joined:
        try:
            await adapter.send_text(chat, texts_fa.group_registered(chat.title, bot_status.missing_permissions))
        except PlatformError as exc:
            logger.warning("Could not send greeting to chat %s: %s", chat.external_id, exc)


async def on_member_status_changed(
    event: ChatMemberUpdated, session: AsyncSession, adapter: PlatformAdapter
) -> None:
    """ورود، خروج یا تغییر نقش یک عضو (فقط وقتی ربات مدیر گروه است دریافت می‌شود)."""
    member = event.new_chat_member
    if member.user.is_bot:
        return

    chat = chat_ref_from(event.chat)
    group, created = await GroupService(session).ensure(chat)
    user = await UserService(session).upsert(user_ref_from(member.user))
    status = member_status_from(member)
    moderation = ModerationService(session, adapter)

    # مسدودی دائمی: کاربر حتی اگر راهی برای ورود پیدا کند، بلافاصله اخراج می‌شود.
    if status == MemberStatus.MEMBER.value and await moderation.enforce_permanent_ban(
        group, chat, user
    ):
        try:
            await adapter.send_text(
                chat,
                texts_fa.permanent_ban_blocked(
                    texts_fa.user_link(
                        user.external_id,
                        texts_fa.display_name(
                            user.first_name, user.last_name, user.username, user.external_id
                        ),
                    )
                ),
            )
        except PlatformError as exc:
            logger.warning("Could not report permanent ban in %s: %s", chat.external_id, exc)
        return

    await MembershipService(session).set_status(group.id, user.id, status)
    # اگر مدیری از منوی خود تلگرام کسی را آزاد/محدود کرده، محدودیت‌های ثبت‌شده را هم‌گام کن.
    await moderation.sync_external(group.id, user.id, status_value(member))

    admin_change = {status_value(event.old_chat_member), status_value(member)} & _ADMIN_STATUSES
    if created or admin_change:
        await refresh_group(session, adapter, group, chat, refresh_bot_status=created)


async def on_group_migrated(message: Message, session: AsyncSession) -> None:
    """گروه معمولی به سوپرگروه تبدیل شده و شناسه‌اش عوض شده است."""
    await GroupService(session).migrate(PLATFORM, message.chat.id, message.migrate_to_chat_id)


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="group_events")
    router.my_chat_member.register(on_bot_status_changed, F.chat.type.in_(GROUP_CHAT_TYPES))
    router.chat_member.register(on_member_status_changed, F.chat.type.in_(GROUP_CHAT_TYPES))
    router.message.register(on_group_migrated, F.migrate_to_chat_id)
    return router
