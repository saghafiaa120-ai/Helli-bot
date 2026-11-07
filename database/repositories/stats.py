from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import DailyMessageCount, User


class StatsRepository:
    """شمارش پیام‌های روزانه (جدول `daily_message_counts`)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_counts(self, rows: Iterable[tuple[str, int, int, date, int]]) -> int:
        """شمارش‌ها را جمع می‌زند: (platform، شناسه گروه، شناسه کاربر، روز، تعداد).

        UPDATE-first انجام می‌شود تا در MySQL و SQLite یکسان کار کند و در برابر
        ساخت هم‌زمان رکورد (IntegrityError) هم مقاوم باشد.
        """
        written = 0
        for platform, group_external_id, user_external_id, day, delta in rows:
            if delta <= 0:
                continue
            conditions = (
                DailyMessageCount.platform == platform,
                DailyMessageCount.group_external_id == group_external_id,
                DailyMessageCount.user_external_id == user_external_id,
                DailyMessageCount.day == day,
            )
            stmt = (
                update(DailyMessageCount)
                .where(*conditions)
                .values(count=DailyMessageCount.count + delta)
            )
            result = await self.session.execute(stmt)
            if not result.rowcount:
                try:
                    async with self.session.begin_nested():
                        self.session.add(
                            DailyMessageCount(
                                platform=platform,
                                group_external_id=group_external_id,
                                user_external_id=user_external_id,
                                day=day,
                                count=delta,
                            )
                        )
                except IntegrityError:
                    await self.session.execute(stmt)
            written += 1
        return written

    async def day_totals(
        self, platform: str, group_external_id: int, day: date
    ) -> tuple[int, int]:
        """(مجموع پیام‌ها، تعداد افراد) برای یک گروه در یک روز."""
        stmt = select(
            func.coalesce(func.sum(DailyMessageCount.count), 0),
            func.count(func.distinct(DailyMessageCount.user_external_id)),
        ).where(
            DailyMessageCount.platform == platform,
            DailyMessageCount.group_external_id == group_external_id,
            DailyMessageCount.day == day,
        )
        total, people = (await self.session.execute(stmt)).one()
        return int(total or 0), int(people or 0)

    async def day_totals_many(
        self, platform: str, group_external_ids: Iterable[int], day: date
    ) -> dict[int, tuple[int, int]]:
        """مثل `day_totals` ولی برای چند گروه با یک کوئری (پنل کاربری)."""
        ids = list(group_external_ids)
        if not ids:
            return {}
        stmt = (
            select(
                DailyMessageCount.group_external_id,
                func.coalesce(func.sum(DailyMessageCount.count), 0),
                func.count(func.distinct(DailyMessageCount.user_external_id)),
            )
            .where(
                DailyMessageCount.platform == platform,
                DailyMessageCount.group_external_id.in_(ids),
                DailyMessageCount.day == day,
            )
            .group_by(DailyMessageCount.group_external_id)
        )
        return {
            int(group_id): (int(total or 0), int(people or 0))
            for group_id, total, people in (await self.session.execute(stmt)).all()
        }

    async def top_users(
        self, platform: str, group_external_id: int, day: date, limit: int = 10
    ) -> list[tuple[str, int]]:
        """فعال‌ترین کاربران روز با نام نمایشی (اگر کاربر در جدول نباشد، شناسه)."""
        stmt = (
            select(
                DailyMessageCount.user_external_id,
                DailyMessageCount.count,
                User.first_name,
                User.last_name,
                User.username,
            )
            .outerjoin(
                User,
                and_(
                    User.platform == DailyMessageCount.platform,
                    User.external_id == DailyMessageCount.user_external_id,
                ),
            )
            .where(
                DailyMessageCount.platform == platform,
                DailyMessageCount.group_external_id == group_external_id,
                DailyMessageCount.day == day,
            )
            .order_by(DailyMessageCount.count.desc(), DailyMessageCount.user_external_id)
            .limit(limit)
        )
        rows: list[tuple[str, int]] = []
        for external_id, count, first_name, last_name, username in (
            await self.session.execute(stmt)
        ).all():
            name = " ".join(part for part in (first_name, last_name) if part).strip()
            if not name:
                name = f"@{username}" if username else str(external_id)
            rows.append((name, int(count)))
        return rows

    async def user_total(self, platform: str, group_external_id: int, user_external_id: int) -> int:
        stmt = select(func.coalesce(func.sum(DailyMessageCount.count), 0)).where(
            DailyMessageCount.platform == platform,
            DailyMessageCount.group_external_id == group_external_id,
            DailyMessageCount.user_external_id == user_external_id,
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def prune(self, before: date) -> int:
        """شمارش‌های قدیمی‌تر از تاریخ داده‌شده را حذف می‌کند."""
        result = await self.session.execute(
            delete(DailyMessageCount).where(DailyMessageCount.day < before)
        )
        return int(result.rowcount or 0)
