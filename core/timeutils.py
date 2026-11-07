"""ابزارهای زمان. همه زمان‌ها در دیتابیس به‌صورت UTC (بدون tzinfo) ذخیره می‌شوند."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """زمان فعلی UTC بدون tzinfo؛ سازگار با ستون‌های DATETIME در MySQL."""
    return datetime.now(UTC).replace(tzinfo=None)
