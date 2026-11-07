from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.timeutils import utcnow
from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK, TimestampMixin


class GroupAdmin(TimestampMixin, Base):
    """مدیر یک گروه.

    platform_role: نقش اعلام‌شده توسط پلتفرم (creator | admin) یا NULL برای نقش‌هایی که
    فقط داخل حلی بات تعریف شده‌اند. helli_role: owner | admin | moderator.
    """

    __tablename__ = "group_admins"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_admins_group_id_user_id"),
        Index("ix_group_admins_user_id", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform_role: Mapped[str | None] = mapped_column(String(16))
    permissions: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    helli_role: Mapped[str] = mapped_column(String(16), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
