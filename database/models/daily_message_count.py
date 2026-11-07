from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK


class DailyMessageCount(Base):
    """تعداد پیام‌های یک کاربر در یک روز برای یک گروه.

    عمداً شناسه‌های پلتفرم (نه کلید خارجی داخلی) ذخیره می‌شوند: شمارنده در حافظه
    کار می‌کند و هنگام ذخیره‌سازی دسته‌ای نباید برای هر پیام چند SELECT بزند.
    نام نمایشی هنگام گزارش از جدول `users` خوانده می‌شود.
    """

    __tablename__ = "daily_message_counts"
    __table_args__ = (
        # نام کوتاه: نام خودکار از سقف ۶۴ کاراکتری MySQL رد می‌شود.
        UniqueConstraint(
            "platform",
            "group_external_id",
            "user_external_id",
            "day",
            name="uq_daily_message_counts_key",
        ),
        Index("ix_daily_message_counts_group_external_id_day", "group_external_id", "day"),
        Index("ix_daily_message_counts_user_external_id", "user_external_id"),
        Index("ix_daily_message_counts_day", "day"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    group_external_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_external_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
