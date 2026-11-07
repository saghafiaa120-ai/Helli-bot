"""کارهای پس‌زمینه: ذخیره شمارنده‌ها، گزارش شبانه و پاک‌سازی.

هر دقیقه یک بار بیدار می‌شود؛ کار سبک است و اگر خطایی رخ دهد فقط لاگ می‌شود تا
حلقه از کار نیفتد.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core import texts_fa
from core.enums import EndReason, RestrictionType
from core.jalali import tehran_now
from database.repositories.moderation import RestrictionRepository
from platforms.base import PlatformAdapter, PlatformError
from platforms.telegram.mapping import chat_ref_from_group
from services.group_service import GroupService
from services.message_counter import MessageCounter
from services.stats_service import RETENTION_DAYS, StatsService, flush_counter

logger = logging.getLogger(__name__)

# گزارش شبانه ساعت ۲۳:۵۹ به وقت تهران (طبق README).
REPORT_HOUR = 23
REPORT_MINUTE = 59
# پاک‌سازی روزانه در ساعات کم‌ترافیک.
HOUSEKEEPING_HOUR = 3


def _seconds_to_next_minute() -> float:
    now = datetime.now()
    return float(60 - now.second) + 0.5


async def stats_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    adapter: PlatformAdapter,
    counter: MessageCounter,
) -> None:
    """حلقه پس‌زمینه آمار و گزارش."""
    last_housekeeping: date | None = None
    while True:
        try:
            await flush_counter(session_factory, counter)
            now = tehran_now()
            await _send_daily_reports(session_factory, adapter, now)
            last_housekeeping = await _housekeeping(session_factory, now, last_housekeeping)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Stats background job failed")
        await asyncio.sleep(_seconds_to_next_minute())


async def _send_daily_reports(
    session_factory: async_sessionmaker[AsyncSession],
    adapter: PlatformAdapter,
    now: datetime,
) -> None:
    if now.hour != REPORT_HOUR or now.minute < REPORT_MINUTE:
        return

    day = now.date()
    marker = day.isoformat()
    async with session_factory() as session:
        groups = GroupService(session)
        stats = StatsService(session)
        for group in await groups.active_groups():
            if await groups.last_daily_report(group.id) == marker:
                continue
            if not await groups.daily_report_enabled(group.id):
                await groups.mark_daily_report(group.id, marker)
                continue

            data = await stats.group_day(group, day)
            if data.total == 0:
                await groups.mark_daily_report(group.id, marker)
                continue

            try:
                await adapter.send_text(
                    chat_ref_from_group(group),
                    texts_fa.daily_report(data.label, data.total, data.people, data.top),
                )
            except PlatformError as exc:
                logger.warning("Daily report failed for group %s: %s", group.id, exc)
                continue
            await groups.mark_daily_report(group.id, marker)
        await session.commit()


async def _housekeeping(
    session_factory: async_sessionmaker[AsyncSession],
    now: datetime,
    last_run: date | None,
) -> date | None:
    """یک بار در روز: حذف آمار قدیمی و بستن محدودیت‌های منقضی."""
    today = now.date()
    if now.hour < HOUSEKEEPING_HOUR or last_run == today:
        return last_run

    async with session_factory() as session:
        cutoff = today - timedelta(days=RETENTION_DAYS)
        removed = await StatsService(session).prune(cutoff)
        restrictions = RestrictionRepository(session)
        expired = await restrictions.expire_due(
            RestrictionType.BAN.value, EndReason.EXPIRED.value
        )
        expired += await restrictions.expire_due(
            RestrictionType.MUTE.value, EndReason.EXPIRED.value
        )
        await session.commit()

    logger.info(
        "Housekeeping done: removed %s old message counts, closed %s expired restrictions",
        removed,
        expired,
    )
    return today
