from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        action: str,
        *,
        group_id: int | None = None,
        actor_user_id: int | None = None,
        target_user_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            group_id=group_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            details=details,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
