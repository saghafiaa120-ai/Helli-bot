from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK, TimestampMixin


class GroupMember(TimestampMixin, Base):
    """عضویت یک کاربر در یک گروه. status: member | left | banned."""

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_id_user_id"),
        Index("ix_group_members_group_id_status", "group_id", "status"),
        Index("ix_group_members_user_id", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member", server_default=text("'member'")
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime)
    left_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)
