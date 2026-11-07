from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AuditAction
from database.repositories.audit import AuditRepository


class AuditService:
    """ثبت گزارش اقدامات مهم (در همان تراکنش عملیات اصلی)."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = AuditRepository(session)

    async def log(
        self,
        action: AuditAction,
        *,
        group_id: int | None = None,
        actor_user_id: int | None = None,
        target_user_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self._repo.add(
            action.value,
            group_id=group_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            details=details,
        )
