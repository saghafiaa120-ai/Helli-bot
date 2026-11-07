from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.timeutils import utcnow
from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK, TimestampMixin


class Group(TimestampMixin, Base):
    """یک گروه در یک پلتفرم. با (platform, external_id) یکتا است."""

    __tablename__ = "chat_groups"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_chat_groups_platform_external_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    # آیا ربات هنوز عضو گروه است؟
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    bot_is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    member_count: Mapped[int | None] = mapped_column(Integer)
    # آخرین زمانی که ربات به گروه اضافه شد.
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime)
