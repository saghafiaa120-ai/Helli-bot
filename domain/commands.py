"""تشخیص و تجزیه دستورها (مستقل از پلتفرم).

هر دستور هم با اسلش (`/ban`) و هم با معادل فارسی بدون اسلش («مسدود») کار می‌کند.
این ماژول هیچ وابستگی‌ای به تلگرام ندارد تا بدون نصب aiogram هم تست شود.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.textnorm import en_digits, fa_digits, normalize

# تلگرام کمتر از ۳۰ ثانیه را «دائمی» حساب می‌کند و بیشتر از ۳۶۶ روز را نمی‌پذیرد.
MIN_DURATION_SECONDS = 30
MAX_DURATION_SECONDS = 366 * 86400

# همه دستورهایی که واقعاً پیاده‌سازی شده‌اند. راهنما و فهرست دستورهای ربات از
# همین فهرست ساخته می‌شود تا هیچ دستور نمایشی/غیرفعالی به کاربر نشان داده نشود.
SLASH_COMMANDS: tuple[str, ...] = (
    "start",
    "help",
    "panel",
    "ban",
    "unban",
    "mute",
    "unmute",
    "kick",
    "warn",
    "unwarn",
    "info",
    "warnings",
    "stats",
    "dailystats",
)

# دستورهایی که به یک کاربر هدف نیاز دارند (Reply، شناسه عددی یا @نام‌کاربری).
TARGET_COMMANDS = frozenset(
    {"ban", "unban", "mute", "unmute", "kick", "warn", "unwarn", "info", "warnings"}
)

# دستورهایی که مدت‌زمان می‌پذیرند.
TIMED_COMMANDS = frozenset({"ban", "mute"})

# دستورهایی که فقط مدیران گروه می‌توانند اجرا کنند.
ADMIN_COMMANDS = frozenset(
    {"ban", "unban", "mute", "unmute", "kick", "warn", "unwarn", "warnings", "stats", "dailystats"}
)

PERSIAN_ALIASES: dict[str, str] = {
    "پنل": "panel",
    "مسدود": "ban",
    "بن": "ban",
    "رفع مسدودی": "unban",
    "آنبن": "unban",
    "سکوت": "mute",
    "میوت": "mute",
    "رفع سکوت": "unmute",
    "آنمیوت": "unmute",
    "اخراج": "kick",
    "کیک": "kick",
    "اخطار": "warn",
    "حذف اخطار": "unwarn",
    "اطلاعات": "info",
    "اخطارها": "warnings",
    "آمار": "stats",
    "امار": "stats",
    "آمار شبانه": "dailystats",
}

# عمداً بلندترین عبارت اول تطبیق داده می‌شود تا «رفع مسدودی» به‌جای «مسدود» گرفته شود.
_ALIASES_BY_LENGTH = tuple(sorted(PERSIAN_ALIASES, key=len, reverse=True))

_PERMANENT_WORDS = frozenset({"دائمی", "دایمی", "همیشگی", "ابد", "permanent", "forever"})

_UNIT_SECONDS: dict[str, int] = {
    "s": 1,
    "ثانیه": 1,
    "m": 60,
    "دقیقه": 60,
    "h": 3600,
    "ساعت": 3600,
    "d": 86400,
    "روز": 86400,
    "w": 604800,
    "هفته": 604800,
    "ماه": 2592000,
    "سال": 31536000,
}

_DURATION_RE = re.compile(r"^(\d{1,4})\s*(ثانیه|دقیقه|ساعت|روز|هفته|ماه|سال|[smhdw])$")


class DurationTooShort(ValueError):
    """مدت کوتاه‌تر از حد مجاز."""


class DurationTooLong(ValueError):
    """مدت بلندتر از حد مجاز."""


@dataclass(frozen=True, slots=True)
class ParsedArgs:
    """آرگومان‌های یک دستور مدیریتی.

    target: شناسه عددی یا `@نام‌کاربری` (اگر با Reply کار شود None است).
    duration: ثانیه؛ None یعنی دائمی یا ذکر نشده.
    reason: متن باقی‌مانده.
    """

    target: str | None = None
    duration: int | None = None
    reason: str | None = None
    duration_given: bool = False

    @property
    def is_permanent(self) -> bool:
        """بدون مدت یا با کلمه «دائمی» → دائمی."""
        return self.duration is None


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    name: str
    args: ParsedArgs
    is_alias: bool = False


def parse_duration(token: str) -> tuple[bool, int | None]:
    """یک تک‌واژه مدت‌زمان را تجزیه می‌کند.

    خروجی: (تشخیص داده شد؟، ثانیه). «دائمی» → (True, None).
    """
    word = en_digits(normalize(token)).lower()
    if word in _PERMANENT_WORDS:
        return True, None
    match = _DURATION_RE.match(word)
    if match is None:
        return False, None
    amount, unit = int(match.group(1)), match.group(2)
    return True, amount * _UNIT_SECONDS[unit]


def validate_duration(seconds: int | None) -> None:
    """بازه مجاز مدت‌زمان را بررسی می‌کند (None یعنی دائمی و مجاز است)."""
    if seconds is None:
        return
    if seconds < MIN_DURATION_SECONDS:
        raise DurationTooShort(str(seconds))
    if seconds > MAX_DURATION_SECONDS:
        raise DurationTooLong(str(seconds))


def duration_label(seconds: int | None) -> str | None:
    """نمایش خوانای مدت: «۲ ساعت»، «۱۰ دقیقه»، None برای دائمی."""
    if seconds is None:
        return None
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, sec = divmod(rest, 60)
    if days:
        label = f"{fa_digits(str(days))} روز"
        if hours:
            label += f" و {fa_digits(str(hours))} ساعت"
        return label
    if hours:
        label = f"{fa_digits(str(hours))} ساعت"
        if minutes:
            label += f" و {fa_digits(str(minutes))} دقیقه"
        return label
    if minutes:
        return f"{fa_digits(str(minutes))} دقیقه"
    return f"{fa_digits(str(sec))} ثانیه"


def parse_args(args: str) -> ParsedArgs:
    """آرگومان‌های بعد از نام دستور را می‌شکند.

    ترتیب دلخواه: [هدف] [مدت] [دلیل]. هر بخشی که نباشد رد می‌شود؛ پس هم
    `/ban 1d تبلیغات` و هم `/ban @ali 1d تبلیغات` و هم `/ban تبلیغات` کار می‌کنند.
    """
    tokens = normalize(args).split()
    target: str | None = None

    if tokens:
        first = tokens[0]
        digits = en_digits(first)
        if first.startswith("@") and len(first) > 1:
            target = first
            tokens = tokens[1:]
        elif digits.isdigit() and len(digits) >= 5:
            target = digits
            tokens = tokens[1:]

    duration: int | None = None
    duration_given = False
    if tokens:
        found, seconds = parse_duration(tokens[0])
        if found:
            duration, duration_given = seconds, True
            tokens = tokens[1:]
        elif len(tokens) >= 2:
            # «۱۰ دقیقه» با فاصله بین عدد و یکا.
            found, seconds = parse_duration(tokens[0] + tokens[1])
            if found:
                duration, duration_given = seconds, True
                tokens = tokens[2:]

    reason = " ".join(tokens).strip() or None
    return ParsedArgs(target=target, duration=duration, reason=reason, duration_given=duration_given)


def split_command(text: str) -> tuple[str | None, str, bool]:
    """متن پیام را به (نام دستور، آرگومان‌ها، آیا معادل فارسی است) تبدیل می‌کند."""
    raw = text.strip()
    if not raw:
        return None, "", False

    if raw.startswith("/"):
        parts = raw[1:].split(maxsplit=1)
        name = parts[0].split("@", 1)[0].lower()  # /ban@MyBot
        rest = parts[1] if len(parts) > 1 else ""
        return (name if name in SLASH_COMMANDS else None), rest.strip(), False

    normalized = normalize(raw)
    for alias in _ALIASES_BY_LENGTH:
        if normalized == alias:
            return PERSIAN_ALIASES[alias], "", True
        if normalized.startswith(alias + " "):
            return PERSIAN_ALIASES[alias], normalized[len(alias) + 1 :].strip(), True
    return None, "", False


def parse_command(text: str) -> ParsedCommand | None:
    """دستور کامل با آرگومان‌های تجزیه‌شده؛ اگر متن دستور نباشد None."""
    name, rest, is_alias = split_command(text)
    if name is None:
        return None
    return ParsedCommand(name=name, args=parse_args(rest), is_alias=is_alias)


def is_alias_message(text: str) -> bool:
    """آیا این پیام یک دستور فارسی بدون اسلش است؟"""
    name, _, is_alias = split_command(text)
    return is_alias and name is not None


def command_list_for_help() -> tuple[str, ...]:
    return SLASH_COMMANDS
