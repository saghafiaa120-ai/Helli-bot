from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.timeutils import utcnow
from database.models import Warning


class WarningRepository:
    """اخطارهای کاربران در هر گروه (جدول `warnings`)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        group_id: int,
        user_id: int,
        *,
        actor_user_id: int | None,
        reason: str | None,
    ) -> Warning:
        row = Warning(
            group_id=group_id,
            user_id=user_id,
            actor_user_id=actor_user_id,
            reason=reason,
            is_active=True,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def count_active(self, group_id: int, user_id: int) -> int:
        stmt = select(func.count(Warning.id)).where(
            Warning.group_id == group_id,
            Warning.user_id == user_id,
            Warning.is_active.is_(True),
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def list_active(self, group_id: int, user_id: int) -> list[Warning]:
        stmt = (
            select(Warning)
            .where(
                Warning.group_id == group_id,
                Warning.user_id == user_id,
                Warning.is_active.is_(True),
            )
            .order_by(Warning.created_at.desc(), Warning.id.desc())
        )
        return list((await self.session.execute(stmt)).scalars())

    async def list_recent(self, group_id: int, user_id: int, limit: int = 10) -> list[Warning]:
        """همه اخطارها (فعال و لغوشده) برای نمایش تاریخچه."""
        stmt = (
            select(Warning)
            .where(Warning.group_id == group_id, Warning.user_id == user_id)
            .order_by(Warning.created_at.desc(), Warning.id.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def revoke(
        self, row: Warning, *, revoked_by_user_id: int | None, reason: str
    ) -> Warning:
        row.is_active = False
        row.revoked_at = utcnow()
        row.revoked_by_user_id = revoked_by_user_id
        row.end_reason = reason
        await self.session.flush()
        return row

    async def revoke_all(
        self, group_id: int, user_id: int, *, revoked_by_user_id: int | None, reason: str
    ) -> int:
        """همه اخطارهای فعال را می‌بندد (مثلاً وقتی به سقف رسیدند و به سکوت تبدیل شدند)."""
        now = utcnow()
        stmt = (
            update(Warning)
            .where(
                Warning.group_id == group_id,
                Warning.user_id == user_id,
                Warning.is_active.is_(True),
            )
            .values(
                is_active=False,
                revoked_at=now,
                revoked_by_user_id=revoked_by_user_id,
                end_reason=reason,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)
