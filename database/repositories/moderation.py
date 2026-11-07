from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.timeutils import utcnow
from database.models import ModerationAction, Restriction


class ModerationActionRepository:
    """سابقه اقدامات مدیریتی (جدول `moderation_actions`)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        action: str,
        *,
        group_id: int | None = None,
        actor_user_id: int | None = None,
        target_user_id: int | None = None,
        duration_seconds: int | None = None,
        reason: str | None = None,
    ) -> ModerationAction:
        entry = ModerationAction(
            action=action,
            group_id=group_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            duration_seconds=duration_seconds,
            reason=reason,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry


class RestrictionRepository:
    """محدودیت‌های فعال و تاریخچه آن‌ها (جدول `restrictions`)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        group_id: int,
        user_id: int,
        kind: str,
        *,
        until: datetime | None,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> Restriction:
        row = Restriction(
            group_id=group_id,
            user_id=user_id,
            kind=kind,
            until=until,
            reason=reason,
            created_by_user_id=created_by_user_id,
            is_active=True,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_active(
        self, group_id: int, user_id: int, kind: str | None = None
    ) -> list[Restriction]:
        """محدودیت‌هایی که هنوز منقضی نشده‌اند."""
        now = utcnow()
        stmt = select(Restriction).where(
            Restriction.group_id == group_id,
            Restriction.user_id == user_id,
            Restriction.is_active.is_(True),
            (Restriction.until.is_(None)) | (Restriction.until > now),
        )
        if kind is not None:
            stmt = stmt.where(Restriction.kind == kind)
        return list((await self.session.execute(stmt)).scalars())

    async def get_active(
        self, group_id: int, user_id: int, kind: str
    ) -> Restriction | None:
        rows = await self.list_active(group_id, user_id, kind)
        return rows[0] if rows else None

    async def end(self, row: Restriction, reason: str) -> Restriction:
        row.is_active = False
        row.ended_at = utcnow()
        row.end_reason = reason
        await self.session.flush()
        return row

    async def end_active(
        self, group_id: int, user_id: int, kind: str, reason: str
    ) -> int:
        """همه محدودیت‌های فعال از این نوع را می‌بندد و تعدادشان را برمی‌گرداند."""
        now = utcnow()
        stmt = (
            update(Restriction)
            .where(
                Restriction.group_id == group_id,
                Restriction.user_id == user_id,
                Restriction.kind == kind,
                Restriction.is_active.is_(True),
            )
            .values(is_active=False, ended_at=now, end_reason=reason)
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)

    async def expire_due(self, kind: str, reason: str) -> int:
        """محدودیت‌هایی که مدتشان گذشته را «منقضی» علامت می‌زند."""
        now = utcnow()
        stmt = (
            update(Restriction)
            .where(
                Restriction.kind == kind,
                Restriction.is_active.is_(True),
                Restriction.until.is_not(None),
                Restriction.until <= now,
            )
            .values(is_active=False, ended_at=now, end_reason=reason)
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)
