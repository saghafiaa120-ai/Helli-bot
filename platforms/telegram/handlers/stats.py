"""آمار پیام‌های گروه و تنظیم گزارش شبانه."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from core import texts_fa
from core.config import Settings
from domain.commands import ParsedCommand
from platforms.telegram.filters import TextCommand
from platforms.telegram.guards import load_group_context
from services.group_service import GroupService
from services.stats_service import StatsService

_ON = frozenset({"on", "روشن", "بله", "1", "true", "فعال"})
_OFF = frozenset({"off", "خاموش", "نه", "0", "false", "غیرفعال"})


async def on_stats(
    message: Message, parsed: ParsedCommand, session: AsyncSession, config: Settings
) -> None:
    ctx = await load_group_context(message, session, config)
    if ctx is None:
        return
    stats = await StatsService(session).group_day(ctx.group)
    await message.answer(texts_fa.stats_today(stats.label, stats.total, stats.people, stats.top))


async def on_dailystats(
    message: Message, parsed: ParsedCommand, session: AsyncSession, config: Settings
) -> None:
    ctx = await load_group_context(message, session, config)
    if ctx is None:
        return

    groups = GroupService(session)
    choice = (parsed.args.reason or "").strip().lower()

    if choice in _ON:
        await groups.set_daily_report(ctx.group.id, True)
        await message.answer(texts_fa.dailystats_changed(True))
        return
    if choice in _OFF:
        await groups.set_daily_report(ctx.group.id, False)
        await message.answer(texts_fa.dailystats_changed(False))
        return

    enabled = await groups.daily_report_enabled(ctx.group.id)
    await message.answer(texts_fa.dailystats_status(enabled))


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="stats")
    router.message.register(on_stats, TextCommand("stats"))
    router.message.register(on_dailystats, TextCommand("dailystats"))
    return router
