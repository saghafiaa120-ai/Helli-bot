from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.timeutils import utcnow
from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK


class Warning(Base):
    """اخطار ثبت‌شده برای یک کاربر. اخطار لغوشده حذف نمی‌شود، فقط غیرفعال می‌شود."""

    __tablename__ = "warnings"
    __table_args__ = (
        Index("ix_warnings_group_id_user_id_is_active", "group_id", "user_id", "is_active"),
        Index("ix_warnings_group_id_created_at", "group_id", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="SET NULL")
    )
    # مقدار EndReason برای اخطار لغوشده
    end_reason: Mapped[str | None] = mapped_column(String(16))
