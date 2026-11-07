"""پنل کاربری دکمه‌ای.

دو حالت دارد:
- داخل گروه: پنل مدیریت همان گروه (فقط برای مدیران) — آمار، اطلاعات خودتان و تنظیمات.
- در گفتگوی خصوصی: فهرست گروه‌هایی که کاربر در آن‌ها مدیر است و تنظیمات هر گروه.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from core import texts_fa
from core.config import Settings
from core.jalali import format_datetime, format_until
from core.permissions import is_global_owner
from database.models import Group, User
from domain.commands import ParsedCommand, duration_label
from platforms.base import PlatformAdapter
from platforms.telegram import panel_keyboards as keyboards
from platforms.telegram import ui
from platforms.telegram.filters import TextCommand
from platforms.telegram.guards import GroupContext, load_group_context, resolve_actor
from platforms.telegram.help_keyboards import help_keyboard
from platforms.telegram.mapping import GROUP_CHAT_TYPES, chat_ref_from, user_ref_from
from platforms.telegram.resilience import with_retry
from services.admin_service import AdminService
from services.group_service import GroupService
from services.moderation_service import Actor, ModerationService
from services.stats_service import StatsService
from services.user_service import UserService

logger = logging.getLogger(__name__)

# چرخه مقادیر تنظیمات با هر بار زدن دکمه.
WARN_LIMIT_CYCLE = (3, 5, 10, 0)
WARN_MUTE_CYCLE = (3600, 21600, 86400, 604800)


def _display(user: User) -> str:
    return texts_fa.display_name(user.first_name, user.last_name, user.username, user.external_id)


async def _managed_groups(session: AsyncSession, tg_user: TgUser, config: Settings) -> list[Group]:
    """گروه‌هایی که کاربر در آن‌ها مدیر است (مالک ربات: همه گروه‌های فعال)."""
    groups = GroupService(session)
    if is_global_owner(tg_user.id, config.owner_ids):
        return await groups.active_groups()
    user = await UserService(session).upsert(user_ref_from(tg_user))
    group_ids = await AdminService(session).list_group_ids_for_user(user.id)
    return [group for group in await groups.groups_by_ids(group_ids) if group.is_active]


async def _group_panel(
    session: AsyncSession, group: Group, actor: Actor
) -> tuple[str, InlineKeyboardMarkup]:
    stats = await StatsService(session).group_day(group)
    settings = await GroupService(session).moderation_settings(group.id)
    text = texts_fa.panel_group(
        title=group.title,
        role_key=actor.role.value if actor.role else "member",
        member_count=group.member_count,
        today_total=stats.total,
        today_people=stats.people,
        warn_limit=settings.warn_limit,
    )
    return text, keyboards.group_panel_keyboard(group.id)


async def _private_panel(
    session: AsyncSession, tg_user: TgUser, config: Settings
) -> tuple[str, InlineKeyboardMarkup]:
    user = await UserService(session).upsert(user_ref_from(tg_user))
    groups = await _managed_groups(session, tg_user, config)
    totals = await StatsService(session).groups_day(groups)
    total = sum(day_total for day_total, _ in totals.values())
    people = sum(people for _, people in totals.values())
    text = texts_fa.panel_private(
        name=_display(user),
        group_count=len(groups),
        today_total=total,
        today_people=people,
    )
    return text, keyboards.private_panel_keyboard(bool(groups))


async def _settings_view(session: AsyncSession, group: Group) -> tuple[str, InlineKeyboardMarkup]:
    groups = GroupService(session)
    settings = await groups.moderation_settings(group.id)
    daily = await groups.daily_report_enabled(group.id)
    mute_label = duration_label(settings.warn_mute_seconds)
    text = texts_fa.panel_settings(
        title=group.title,
        daily_report=daily,
        warn_limit=settings.warn_limit,
        warn_mute_label=mute_label,
        confirm_sensitive=settings.confirm_sensitive_actions,
    )
    return text, keyboards.settings_keyboard(
        group.id,
        daily_report=daily,
        warn_limit=settings.warn_limit,
        warn_mute_label=mute_label,
        confirm_sensitive=settings.confirm_sensitive_actions,
    )


async def _render(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """پنل را ویرایش می‌کند و در هر شرایطی به دکمه پاسخ می‌دهد.

    اگر ویرایش ممکن نشد (قطعی شبکه، حذف‌شدن پیام)، نسخه تازه فرستاده می‌شود تا
    کاربر بدون پاسخ نماند.
    """
    try:
        await ui.safe_edit(
            callback.message, text, reply_markup=markup, fallback_send=True
        )
    finally:
        await ui.answer(callback)


async def _authorize(
    session: AsyncSession, config: Settings, tg_user: TgUser | None, group_id: int
) -> tuple[Group, Actor] | None:
    """گروه و نقش کاربر را برای اکشن‌های مخصوص یک گروه برمی‌گرداند."""
    if tg_user is None:
        return None
    group = await GroupService(session).get_by_id(group_id)
    if group is None or not group.is_active:
        return None
    actor = await resolve_actor(session, group, tg_user, config)
    if actor.role is None and not actor.is_global_owner:
        return None
    return group, actor


async def on_panel(
    message: Message, parsed: ParsedCommand, session: AsyncSession, config: Settings
) -> None:
    if message.chat.type in GROUP_CHAT_TYPES:
        ctx = await load_group_context(message, session, config)
        if ctx is None:
            return
        text, markup = await _group_panel(session, ctx.group, ctx.actor)
        await message.answer(text, reply_markup=markup)
        return

    if message.from_user is None:
        return
    text, markup = await _private_panel(session, message.from_user, config)
    await message.answer(text, reply_markup=markup)


async def on_panel_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    adapter: PlatformAdapter,
    config: Settings,
) -> None:
    parts = (callback.data or "").split(":")
    action = parts[1] if len(parts) > 1 else "home"

    if action == "close":
        await _close(callback)
        return

    if action == "home":
        if callback.message is not None and callback.message.chat.type in GROUP_CHAT_TYPES:
            ctx = await _context_from_chat(session, config, callback)
            if ctx is None:
                await ui.answer(callback, texts_fa.panel_not_admin(), alert=True)
                return
            text, markup = await _group_panel(session, ctx.group, ctx.actor)
        else:
            if callback.from_user is None:
                await ui.answer(callback)
                return
            text, markup = await _private_panel(session, callback.from_user, config)
        await _render(callback, text, markup)
        return

    if action == "help":
        await _render(callback, texts_fa.help_text(), help_keyboard("main"))
        return

    if action == "groups":
        if callback.from_user is None:
            await ui.answer(callback)
            return
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        await _render_groups(callback, session, config, callback.from_user, page)
        return

    if action == "me":
        await _render_me(callback, session, adapter, config)
        return

    # اکشن‌های وابسته به یک گروه: group / stats / settings / toggle
    if len(parts) < 3 or not parts[2].lstrip("-").isdigit():
        await ui.answer(callback)
        return
    group_id = int(parts[2])
    authorized = await _authorize(session, config, callback.from_user, group_id)
    if authorized is None:
        await ui.answer(callback, texts_fa.panel_not_admin(), alert=True)
        return
    group, actor = authorized

    if action == "group":
        text, markup = await _group_panel(session, group, actor)
        await _render(callback, text, markup)
        return

    if action == "stats":
        stats = await StatsService(session).group_day(group)
        text = texts_fa.stats_today(stats.label, stats.total, stats.people, stats.top)
        await _render(callback, text, keyboards.back_keyboard(group.id))
        return

    if action == "settings":
        text, markup = await _settings_view(session, group)
        await _render(callback, text, markup)
        return

    if action == "toggle":
        key = parts[3] if len(parts) > 3 else ""
        await _toggle(session, group, key)
        text, markup = await _settings_view(session, group)
        await _render(callback, text, markup)
        return

    await ui.answer(callback)


async def _context_from_chat(
    session: AsyncSession, config: Settings, callback: CallbackQuery
) -> GroupContext | None:
    """ساخت context از پیام دکمه (بدون پاسخ‌دادن به کاربر)."""
    message = callback.message
    if message is None or callback.from_user is None:
        return None

    chat = chat_ref_from(message.chat)
    groups = GroupService(session)
    group, _ = await groups.ensure(chat)
    actor = await resolve_actor(session, group, callback.from_user, config)
    if actor.role is None and not actor.is_global_owner:
        return None
    return GroupContext(
        chat=chat,
        group=group,
        actor=actor,
        settings=await groups.moderation_settings(group.id),
    )


async def _render_groups(
    callback: CallbackQuery,
    session: AsyncSession,
    config: Settings,
    tg_user: TgUser,
    page: int,
) -> None:
    groups = await _managed_groups(session, tg_user, config)
    pages = max(1, -(-len(groups) // keyboards.GROUPS_PAGE_SIZE))
    page = min(max(1, page), pages)
    start = (page - 1) * keyboards.GROUPS_PAGE_SIZE
    chunk = groups[start : start + keyboards.GROUPS_PAGE_SIZE]
    text = texts_fa.panel_groups_list(total=len(groups), page=page, pages=pages)
    markup = keyboards.groups_keyboard(
        [(group.id, group.title, group.external_id) for group in chunk], page, pages
    )
    await _render(callback, text, markup)


async def _render_me(
    callback: CallbackQuery,
    session: AsyncSession,
    adapter: PlatformAdapter,
    config: Settings,
) -> None:
    message = callback.message
    if message is None or callback.from_user is None:
        await ui.answer(callback)
        return
    if message.chat.type not in GROUP_CHAT_TYPES:
        await ui.answer(callback, texts_fa.panel_self_only(), alert=True)
        return

    ctx = await _context_from_chat(session, config, callback)
    if ctx is None:
        await ui.answer(callback, texts_fa.panel_not_admin(), alert=True)
        return

    service = ModerationService(session, adapter)
    info = await service.user_info(
        group=ctx.group,
        target=ctx.actor.user,
        actor=ctx.actor,
        total_messages=await StatsService(session).user_total(
            ctx.group, ctx.actor.user.external_id
        ),
    )
    text = texts_fa.info_card(
        name_link=texts_fa.user_link(info.user.external_id, _display(info.user)),
        external_id=info.user.external_id,
        username=info.user.username,
        role_key=info.role_key,
        member_status=info.member_status,
        warning_count=info.warning_count,
        warn_limit=ctx.settings.warn_limit,
        restriction_lines=[
            texts_fa.restriction_line(kind, format_until(until))
            for kind, until in info.restrictions
        ],
        first_seen=format_datetime(info.first_seen) if info.first_seen else None,
        joined_at=format_datetime(info.joined_at) if info.joined_at else None,
        last_active=format_datetime(info.last_active) if info.last_active else None,
        total_messages=info.total_messages,
    )
    await _render(callback, text, keyboards.back_keyboard(ctx.group.id))


async def _toggle(session: AsyncSession, group: Group, key: str) -> None:
    groups = GroupService(session)
    settings = await groups.moderation_settings(group.id)

    if key == "daily":
        await groups.set_daily_report(group.id, not await groups.daily_report_enabled(group.id))
    elif key == "confirm":
        await groups.set_confirm_sensitive(group.id, not settings.confirm_sensitive_actions)
    elif key == "warnlimit":
        await groups.set_warn_settings(
            group.id, warn_limit=_next_value(WARN_LIMIT_CYCLE, settings.warn_limit)
        )
    elif key == "warnmute":
        await groups.set_warn_settings(
            group.id, warn_mute_seconds=_next_value(WARN_MUTE_CYCLE, settings.warn_mute_seconds)
        )


def _next_value(cycle: tuple[int, ...], current: int) -> int:
    try:
        index = cycle.index(current)
    except ValueError:
        return cycle[0]
    return cycle[(index + 1) % len(cycle)]


async def _close(callback: CallbackQuery) -> None:
    message = callback.message
    if message is not None:
        try:
            await with_retry(lambda: message.delete(), what="panel delete")
        except Exception:
            # ربات دسترسی حذف پیام ندارد؛ متن را جایگزین می‌کنیم.
            try:
                await with_retry(
                    lambda: message.edit_text(texts_fa.panel_closed()), what="panel close edit"
                )
            except Exception:
                pass
    await ui.answer(callback, texts_fa.panel_closed())


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="panel")
    router.message.register(on_panel, TextCommand("panel"))
    router.callback_query.register(on_panel_callback, F.data.startswith("panel:"))
    return router
