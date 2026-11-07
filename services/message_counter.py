"""شمارنده پیام‌های درحافظه.

نوشتن در دیتابیس به ازای هر پیام گروه، هم کند است و هم بار زیادی روی MySQL
می‌گذارد. بنابراین هر پیام فقط در حافظه شمرده می‌شود و هر ۶۰ ثانیه (و هنگام
خاموش شدن ربات) یک‌جا ذخیره می‌شود. فقط تعداد ذخیره می‌شود، نه متن پیام.
"""

from __future__ import annotations

from datetime import date

CountKey = tuple[str, int, int, date]  # (platform، شناسه گروه، شناسه کاربر، روز تهران)

# اگر ذخیره‌سازی مدتی شکست بخورد، حافظه نباید بی‌نهایت رشد کند.
MAX_PENDING_KEYS = 100_000


class MessageCounter:
    """شمارنده ساده و بدون I/O برای پیام‌های گروه."""

    __slots__ = ("_counts",)

    def __init__(self) -> None:
        self._counts: dict[CountKey, int] = {}

    def add(self, platform: str, group_external_id: int, user_external_id: int, day: date) -> None:
        key = (platform, group_external_id, user_external_id, day)
        self._counts[key] = self._counts.get(key, 0) + 1

    def drain(self) -> list[tuple[str, int, int, date, int]]:
        """همه شمارش‌ها را برمی‌گرداند و حافظه را خالی می‌کند."""
        rows = [(p, g, u, d, c) for (p, g, u, d), c in self._counts.items()]
        self._counts.clear()
        return rows

    def restore(self, rows: list[tuple[str, int, int, date, int]]) -> None:
        """اگر ذخیره‌سازی شکست خورد، شمارش‌ها را برمی‌گرداند تا تلاش بعدی از دست نروند."""
        for platform, group_id, user_id, day, count in rows:
            key = (platform, group_id, user_id, day)
            self._counts[key] = self._counts.get(key, 0) + count
        if len(self._counts) > MAX_PENDING_KEYS:
            self._counts.clear()

    def pending(self) -> int:
        """تعداد کلیدهای ذخیره‌نشده (برای لاگ و مانیتورینگ)."""
        return len(self._counts)

    def total(self) -> int:
        """مجموع پیام‌های شمرده‌شده و ذخیره‌نشده."""
        return sum(self._counts.values())
