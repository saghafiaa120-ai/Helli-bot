"""آمار پیام‌های گروه و ذخیره‌سازی شمارنده‌های درحافظه."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.jalali import day_label, tehran_day
from core.timeutils import utcnow
from database.models import Group
from database.repositories.stats import StatsRepository
from services.message_counter import MessageCounter

logger = logging.getLogger(__name__)

# شمارش‌ها ۹۰ روز نگه داشته می‌شوند.
RETENTION_DAYS = 90


@dataclass(frozen=True, slots=True)
class DayStats:
    """آمار یک روز از یک گروه."""

    day: date
    total: int
    people: int
    top: tuple[tuple[str, int], ...] = ()

    @property
    def label(self) -> str:
        return day_label(self.day)


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = StatsRepository(session)

    async def group_day(self, group: Group, day: date | None = None, limit: int = 10) -> DayStats:
        """آمار یک روز گروه؛ پیش‌فرض «امروز به وقت تهران»."""
        target = day or tehran_day(utcnow())
        total, people = await self._repo.day_totals(group.platform, group.external_id, target)
        top = tuple(await self._repo.top_users(group.platform, group.external_id, target, limit))
        return DayStats(day=target, total=total, people=people, top=top)

    async def groups_day(self, groups: list[Group], day: date | None = None) -> dict[int, tuple[int, int]]:
        """آمار امروز چند گروه با یک کوئری؛ کلید = شناسه داخلی گروه."""
        target = day or tehran_day(utcnow())
        if not groups:
            return {}
        platform = groups[0].platform
        totals = await self._repo.day_totals_many(
            platform, [group.external_id for group in groups], target
        )
        return {group.id: totals.get(group.external_id, (0, 0)) for group in groups}

    async def user_total(self, group: Group, user_external_id: int) -> int:
        """مجموع پیام‌های یک کاربر در این گروه (کل بازه نگهداری)."""
        return await self._repo.user_total(group.platform, group.external_id, user_external_id)

    async def prune(self, before: date) -> int:
        return await self._repo.prune(before)


async def flush_counter(
    session_factory: async_sessionmaker[AsyncSession], counter: MessageCounter
) -> int:
    """شمارنده‌های درحافظه را در دیتابیس می‌نویسد.

    خطا فقط لاگ می‌شود (شمارش آمار نباید پردازش پیام‌ها را متوقف کند) و
    شمارش‌ها برمی‌گردند تا در تلاش بعدی نوشته شوند.
    """
    rows = counter.drain()
    if not rows:
        return 0
    try:
        async with session_factory() as session:
            written = await StatsRepository(session).add_counts(rows)
            await session.commit()
        return written
    except Exception:
        counter.restore(rows)
        logger.exception("Could not flush %s message-count rows", len(rows))
        return 0
