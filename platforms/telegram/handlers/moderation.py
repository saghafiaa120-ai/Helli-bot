"""دستورهای مدیریت کاربران: مسدود، سکوت، اخراج، اخطار و اطلاعات."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core import texts_fa
from core.config import Settings
from core.jalali import format_datetime, format_until
from database.models import User
from domain.commands import (
    TARGET_COMMANDS,
    DurationTooLong,
    DurationTooShort,
    ParsedCommand,
    duration_label,
    validate_duration,
)
from platforms.base import PlatformAdapter
from platforms.telegram import ui
from platforms.telegram.confirmations import PendingConfirmations
from platforms.telegram.filters import TextCommand
from platforms.telegram.guards import (
    GroupContext,
    TargetError,
    load_group_context,
    resolve_actor,
    resolve_target,
)
from platforms.telegram.mapping import chat_ref_from_group
from platforms.telegram.panel_keyboards import confirm_keyboard
from services.group_service import GroupService
from services.moderation_service import ModerationError, ModerationService, UserInfo
from services.stats_service import StatsService
from services.user_service import UserService

logger = logging.getLogger(__name__)


def _display(user: User) -> str:
    return texts_fa.display_name(user.first_name, user.last_name, user.username, user.external_id)


def _link(user: User) -> str:
    return texts_fa.user_link(user.external_id, _display(user))


def _info_text(info: UserInfo, warn_limit: int) -> str:
    return texts_fa.info_card(
        name_link=_link(info.user),
        external_id=info.user.external_id,
        username=info.user.username,
        role_key=info.role_key,
        member_status=info.member_status,
        warning_count=info.warning_count,
        warn_limit=warn_limit,
        restriction_lines=[
            texts_fa.restriction_line(kind, format_until(until))
            for kind, until in info.restrictions
        ],
        first_seen=format_datetime(info.first_seen) if info.first_seen else None,
        joined_at=format_datetime(info.joined_at) if info.joined_at else None,
        last_active=format_datetime(info.last_active) if info.last_active else None,
        total_messages=info.total_messages,
    )


async def _safe_edit(message: Message | None, text: str, **kwargs: object) -> None:
    """ویرایش پیام با تلاش دوباره در خطاهای گذرا؛ خطای «تغییر نکرده» خطا نیست."""
    await ui.safe_edit(message, text, **kwargs)


async def _target_for(
    message: Message, session: AsyncSession, ctx: GroupContext, parsed: ParsedCommand
) -> User | None:
    """هدف دستور؛ برای /info و /warnings بدون هدف، خود کاربر."""
    if (
        parsed.name in ("info", "warnings")
        and not parsed.args.target
        and message.reply_to_message is None
    ):
        return ctx.actor.user
    try:
        return await resolve_target(message, session, parsed.args)
    except TargetError as exc:
        if exc.kind == "no_target":
            await message.answer(texts_fa.usage(parsed.name))
        else:
            await message.answer(texts_fa.moderation_error(exc.kind, name=exc.value))
        return None


async def on_target_command(
    message: Message,
    parsed: ParsedCommand,
    session: AsyncSession,
    adapter: PlatformAdapter,
    config: Settings,
    pending: PendingConfirmations,
) -> None:
    ctx = await load_group_context(message, session, config)
    if ctx is None:
        return

    name = parsed.name
    args = parsed.args

    if name in ("ban", "mute"):
        try:
            validate_duration(args.duration)
        except DurationTooShort:
            await message.answer(texts_fa.duration_too_short())
            return
        except DurationTooLong:
            await message.answer(texts_fa.duration_too_long())
            return

    target = await _target_for(message, session, ctx, parsed)
    if target is None:
        return

    service = ModerationService(session, adapter)
    try:
        if name == "info":
            stats = StatsService(session)
            info = await service.user_info(
                group=ctx.group,
                target=target,
                actor=ctx.actor,
                total_messages=await stats.user_total(ctx.group, target.external_id),
            )
            await message.answer(_info_text(info, ctx.settings.warn_limit))
            return

        if name == "warnings":
            count, rows = await service.warning_history(ctx.group, target)
            entries = [
                (
                    format_datetime(row.created_at),
                    row.reason or "",
                    issuer,
                    row.is_active,
                )
                for row, issuer in rows
            ]
            await message.answer(
                texts_fa.warnings_list(_link(target), count, ctx.settings.warn_limit, entries)
            )
            return

        if name == "ban":
            # بدون ذکر مدت، مسدودی موقت گروه (پیش‌فرض ۵ ساعت) اعمال می‌شود تا کاربر
            # بعد از آن بتواند برگردد. مسدودی دائمی فقط با نوشتن «دائمی» است.
            duration = args.duration if args.duration_given else ctx.settings.default_ban_seconds
            if duration is None and ctx.settings.confirm_sensitive_actions:
                item = pending.create(
                    kind="ban",
                    group_external_id=ctx.chat.external_id,
                    actor_external_id=ctx.actor_id,
                    target_external_id=target.external_id,
                    target_name=_display(target),
                    reason=args.reason,
                )
                await message.answer(
                    texts_fa.confirm_ban(_link(target), args.reason),
                    reply_markup=confirm_keyboard(item.token),
                )
                return
            outcome = await service.ban(
                group=ctx.group,
                chat=ctx.chat,
                actor=ctx.actor,
                target=target,
                duration_seconds=duration,
                reason=args.reason,
            )
            await message.answer(
                texts_fa.banned(
                    _link(target),
                    duration_label(outcome.duration_seconds),
                    format_until(outcome.until),
                    args.reason,
                )
            )
            return

        if name == "unban":
            lifted = await service.unban(
                group=ctx.group, chat=ctx.chat, actor=ctx.actor, target=target
            )
            await message.answer(
                texts_fa.unbanned(_link(target)) if lifted else texts_fa.not_banned(_link(target))
            )
            return

        if name == "mute":
            outcome = await service.mute(
                group=ctx.group,
                chat=ctx.chat,
                actor=ctx.actor,
                target=target,
                duration_seconds=args.duration,
                reason=args.reason,
            )
            await message.answer(
                texts_fa.muted(
                    _link(target),
                    duration_label(outcome.duration_seconds),
                    format_until(outcome.until),
                    args.reason,
                )
            )
            return

        if name == "unmute":
            lifted = await service.unmute(
                group=ctx.group, chat=ctx.chat, actor=ctx.actor, target=target
            )
            await message.answer(
                texts_fa.unmuted(_link(target)) if lifted else texts_fa.not_muted(_link(target))
            )
            return

        if name == "kick":
            await service.kick(
                group=ctx.group,
                chat=ctx.chat,
                actor=ctx.actor,
                target=target,
                reason=args.reason,
            )
            await message.answer(texts_fa.kicked(_link(target), args.reason))
            return

        if name == "warn":
            outcome = await service.warn(
                group=ctx.group,
                chat=ctx.chat,
                actor=ctx.actor,
                target=target,
                reason=args.reason,
                settings=ctx.settings,
            )
            await message.answer(
                texts_fa.warned(
                    _link(target),
                    outcome.count,
                    outcome.limit,
                    args.reason,
                    auto_mute=duration_label(outcome.auto_mute_seconds),
                    auto_mute_until=format_until(outcome.auto_mute_until),
                    auto_mute_failed=outcome.auto_mute_failed,
                )
            )
            return

        if name == "unwarn":
            remaining = await service.unwarn(group=ctx.group, actor=ctx.actor, target=target)
            await message.answer(texts_fa.unwarned(_link(target), remaining))
            return

    except ModerationError as exc:
        await message.answer(texts_fa.moderation_error(exc.kind))
    except Exception:
        logger.exception("Moderation command %s failed", name)
        await message.answer(texts_fa.internal_error())


async def on_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    adapter: PlatformAdapter,
    config: Settings,
    pending: PendingConfirmations,
) -> None:
    """اجرای مسدودی دائمی پس از تأیید مدیر."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await ui.answer(callback)
        return

    _, action, token = parts
    item = pending.peek(token)
    if item is None:
        await ui.answer(callback, texts_fa.confirm_expired(), alert=True)
        return
    if callback.from_user is None or callback.from_user.id != item.actor_external_id:
        await ui.answer(callback, texts_fa.confirm_not_yours(), alert=True)
        return

    pending.discard(token)

    if action == "no":
        await _safe_edit(callback.message, texts_fa.confirm_cancelled())
        await ui.answer(callback)
        return

    group = await GroupService(session).get_by_external("telegram", item.group_external_id)
    if group is None or not group.is_active:
        await ui.answer(callback, texts_fa.panel_group_unavailable(), alert=True)
        return

    actor = await resolve_actor(session, group, callback.from_user, config)
    target = await UserService(session).get_or_create_by_id("telegram", item.target_external_id)
    service = ModerationService(session, adapter)
    try:
        await service.ban(
            group=group,
            chat=chat_ref_from_group(group),
            actor=actor,
            target=target,
            duration_seconds=None,
            reason=item.reason,
        )
    except ModerationError as exc:
        await ui.answer(callback, texts_fa.moderation_error(exc.kind), alert=True)
        return
    except Exception:
        logger.exception("Confirmed ban failed")
        await ui.answer(callback, texts_fa.internal_error(), alert=True)
        return

    await _safe_edit(
        callback.message, texts_fa.banned(_link(target), None, None, item.reason)
    )
    await ui.answer(callback)


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="moderation")
    router.message.register(on_target_command, TextCommand(*TARGET_COMMANDS))
    router.callback_query.register(on_confirm, F.data.startswith("confirm:"))
    return router
