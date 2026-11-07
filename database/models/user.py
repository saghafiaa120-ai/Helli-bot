from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK, TimestampMixin


class User(TimestampMixin, Base):
    """کاربر یک پلتفرم. فقط داده‌های لازم ذخیره می‌شود (شناسه و نام نمایشی)."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_users_platform_external_id"),
        Index("ix_users_username", "username"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_bot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
