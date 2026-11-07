from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import MYSQL_TABLE_ARGS, Base, BigIntPK, TimestampMixin


class GroupSettings(TimestampMixin, Base):
    """تنظیمات اختصاصی هر گروه (رابطه یک‌به‌یک با گروه)."""

    __tablename__ = "group_settings"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    group_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("chat_groups.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="fa", server_default=text("'fa'")
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Tehran", server_default=text("'Asia/Tehran'")
    )
    confirm_sensitive_actions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    # تنظیمات انعطاف‌پذیر بعدی (فیلترها، قفل‌ها، امنیت) در این ستون JSON ذخیره می‌شوند.
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
