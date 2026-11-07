from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timeutils import utcnow
from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK


class ModerationAction(Base):
    """سابقه همه اقدامات مدیریتی (حتی وقتی بعداً برگردانده شوند).

    با حذف گروه یا کاربر، سابقه می‌ماند (SET NULL) تا گزارش‌ها پاک نشوند.
    """

    __tablename__ = "moderation_actions"
    __table_args__ = (
        Index("ix_moderation_actions_group_id_created_at", "group_id", "created_at"),
        Index("ix_moderation_actions_target_user_id", "target_user_id"),
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
    # مقدار ModerationActionType
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
