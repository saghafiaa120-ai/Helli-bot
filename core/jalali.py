"""تاریخ شمسی و وقت تهران.

در دیتابیس همه زمان‌ها UTC و بدون tzinfo ذخیره می‌شوند (نگاه کنید به
`core.timeutils`). هر جا زمان به کاربر نشان داده می‌شود یا «روز» معنا پیدا می‌کند
(مثل آمار روزانه و گزارش شبانه)، اول به وقت تهران تبدیل و بعد به شمسی نمایش داده
می‌شود.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from core.textnorm import fa_digits

TEHRAN = ZoneInfo("Asia/Tehran")

_MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

# روزهای قبل از شروع هر ماه میلادی (سال غیرکبیسه).
_GREGORIAN_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def tehran_now() -> datetime:
    """زمان فعلی به وقت تهران (آگاه از منطقه زمانی)."""
    return datetime.now(TEHRAN)


def as_utc_aware(value: datetime) -> datetime:
    """زمان ذخیره‌شده در دیتابیس (UTC بدون tzinfo) را آگاه از منطقه می‌کند."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def to_tehran(value: datetime) -> datetime:
    """هر زمانی را به وقت تهران می‌برد."""
    return as_utc_aware(value).astimezone(TEHRAN)


def tehran_day(value: datetime) -> date:
    """روز تقویمی به وقت تهران برای یک زمان UTC."""
    return to_tehran(value).date()


def gregorian_to_jalali(day: date) -> tuple[int, int, int]:
    """تبدیل تاریخ میلادی به شمسی (الگوریتم استاندارد jalaali)."""
    gy, gm, gd = day.year, day.month, day.day
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + 365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        + gd
        + _GREGORIAN_DAYS_BEFORE_MONTH[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_date(day: date) -> str:
    """تاریخ شمسی عددی با ارقام فارسی: «۱۴۰۵/۰۸/۱۶»."""
    jy, jm, jd = gregorian_to_jalali(day)
    return fa_digits(f"{jy}/{jm:02d}/{jd:02d}")


def jalali_long_date(day: date) -> str:
    """تاریخ شمسی خوانا: «۱۶ آبان ۱۴۰۵»."""
    jy, jm, jd = gregorian_to_jalali(day)
    return f"{fa_digits(str(jd))} {_MONTH_NAMES[jm - 1]} {fa_digits(str(jy))}"


def day_label(day: date) -> str:
    """برچسب روز برای گزارش‌ها (تاریخ عددی شمسی)."""
    return jalali_date(day)


def format_time(value: datetime) -> str:
    """ساعت به وقت تهران با ارقام فارسی: «۱۴:۳۰»."""
    local = to_tehran(value)
    return fa_digits(f"{local.hour:02d}:{local.minute:02d}")


def format_datetime(value: datetime) -> str:
    """تاریخ و ساعت به وقت تهران: «۱۴۰۵/۰۸/۱۶ ۱۴:۳۰»."""
    local = to_tehran(value)
    return f"{jalali_date(local.date())} {fa_digits(f'{local.hour:02d}:{local.minute:02d}')}"


def format_until(value: datetime | None) -> str | None:
    """زمان پایان محدودیت؛ None یعنی دائمی."""
    return None if value is None else format_datetime(value)


def seconds_to_tehran_time(seconds: int) -> str:
    """برای نمایش مدت‌های کوتاه به شکل ساعت/دقیقه."""
    minutes, sec = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{fa_digits(str(hours))} ساعت")
    if minutes:
        parts.append(f"{fa_digits(str(minutes))} دقیقه")
    if sec and not hours:
        parts.append(f"{fa_digits(str(sec))} ثانیه")
    return " و ".join(parts) or "۰ ثانیه"


def tehran_midnight(day: date) -> datetime:
    """نیمه‌شب تهران برای یک روز، به UTC بدون tzinfo (هم‌شکل ستون‌های دیتابیس)."""
    local = datetime.combine(day, time.min, tzinfo=TEHRAN)
    return local.astimezone(UTC).replace(tzinfo=None)
