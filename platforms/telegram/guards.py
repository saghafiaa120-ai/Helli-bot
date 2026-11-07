"""بررسی‌های مشترک handlerها: گروه، هویت مدیر، نقش و هدف دستور."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram.types import Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from core import texts_fa
from core.config import Settings
from core.enums import HelliRole
from core.permissions import is_global_owner
from database.models import Group, User
from domain.commands import ParsedArgs
from domain.dto import ChatRef, ModerationSettings
from platforms.telegram.mapping import GROUP_CHAT_TYPES, chat_ref_from, user_ref_from
from services.admin_service import AdminService
from services.group_service import GroupService
from services.moderation_service import Actor
from services.user_service import UserService

logger = logging.getLogger(__name__)

# تلگرام پیام «مدیر ناشناس» را از طرف این حساب می‌فرستد.
ANONYMOUS_BOT_ID = 1087968824
# حساب‌های خدماتی تلگرام (گروه ناشناس، کانال، تلگرام).
SERVICE_USER_IDS = frozenset({ANONYMOUS_BOT_ID, 777000, 136817688})


class TargetError(Exception):
    """هدف دستور قابل تشخیص نیست؛ `kind` نوع پیام مناسب است."""

    def __init__(self, kind: str, value: str | None = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.value = value


@dataclass(frozen=True, slots=True)
class GroupContext:
    chat: ChatRef
    group: Group
    actor: Actor
    settings: ModerationSettings

    @property
    def actor_id(self) -> int:
        return self.actor.external_id


async def resolve_actor(
    session: AsyncSession, group: Group, tg_user: TgUser, config: Settings
) -> Actor:
    """کاربر را در دیتابیس ثبت و نقش/دسترسی‌هایش را در این گروه پیدا می‌کند."""
    user = await UserService(session).upsert(user_ref_from(tg_user))
    admin_row = await AdminService(session).get_admin(group.id, user.id)
    owner = is_global_owner(tg_user.id, config.owner_ids)
    if owner:
        role = HelliRole.OWNER
    elif admin_row is not None:
        role = HelliRole(admin_row.helli_role)
    else:
        role = None
    return Actor(
        user=user,
        role=role,
        is_global_owner=owner,
        permissions=dict(admin_row.permissions or {}) if admin_row else {},
    )


async def load_group_context(
    message: Message,
    session: AsyncSession,
    config: Settings,
    *,
    require_admin: bool = True,
) -> GroupContext | None:
    """شرایط لازم برای دستور گروهی را بررسی می‌کند و در صورت خطا خودش پاسخ می‌دهد."""
    if message.chat.type not in GROUP_CHAT_TYPES:
        await message.answer(texts_fa.only_in_groups())
        return None

    tg_user = message.from_user
    if tg_user is None or tg_user.id == ANONYMOUS_BOT_ID or tg_user.id in SERVICE_USER_IDS:
        await message.answer(texts_fa.anonymous_admin())
        return None

    chat = chat_ref_from(message.chat)
    groups = GroupService(session)
    group, _ = await groups.ensure(chat)
    actor = await resolve_actor(session, group, tg_user, config)

    if require_admin and actor.role is None and not actor.is_global_owner:
        await message.answer(texts_fa.not_authorized())
        return None

    return GroupContext(
        chat=chat,
        group=group,
        actor=actor,
        settings=await groups.moderation_settings(group.id),
    )


async def resolve_target(
    message: Message, session: AsyncSession, args: ParsedArgs
) -> User:
    """کاربر هدف را از شناسه/@نام‌کاربری یا Reply پیدا می‌کند."""
    users = UserService(session)

    if args.target:
        if args.target.startswith("@"):
            username = args.target[1:]
            found = await users.find_by_username("telegram", username)
            if found is None:
                raise TargetError("username_unknown", username)
            return found
        return await users.get_or_create_by_id("telegram", int(args.target))

    replied = message.reply_to_message
    if replied is not None:
        sender = replied.from_user
        if sender is None or sender.id in SERVICE_USER_IDS:
            raise TargetError("target_unresolvable")
        return await users.upsert(user_ref_from(sender))

    raise TargetError("no_target")
