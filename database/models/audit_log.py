from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timeutils import utcnow
from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK


class AuditLog(Base):
    """گزارش اقدامات مهم. با حذف گروه یا کاربر، سابقه می‌ماند (SET NULL)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_group_id_created_at", "group_id", "created_at"),
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    group_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("chat_groups.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="SET NULL")
    )
    target_user_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
