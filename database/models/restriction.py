from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.timeutils import utcnow
from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK


class Restriction(Base):
    """یک محدودیت (مسدودی یا سکوت) روی یک کاربر در یک گروه.

    محدودیت پایان‌یافته حذف نمی‌شود؛ `is_active` صفر و `end_reason` پر می‌شود تا
    سابقه قابل بررسی بماند.
    """

    __tablename__ = "restrictions"
    __table_args__ = (
        Index("ix_restrictions_group_id_user_id_kind", "group_id", "user_id", "kind"),
        Index("ix_restrictions_is_active_until", "is_active", "until"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # مقدار RestrictionType: ban | mute
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    until: Mapped[datetime | None] = mapped_column(DateTime)  # None = دائمی
    reason: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    # مقدار EndReason
    end_reason: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
