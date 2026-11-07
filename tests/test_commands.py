"""تست تجزیه دستورها، مدت‌زمان و تاریخ شمسی (بدون نیاز به aiogram)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from core.jalali import (
    format_datetime,
    gregorian_to_jalali,
    jalali_date,
    tehran_day,
)
from core.textnorm import en_digits, fa_digits, normalize
from domain.commands import (
    DurationTooLong,
    DurationTooShort,
    duration_label,
    parse_command,
    parse_duration,
    validate_duration,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("۱۲۳", "123"),
        ("٤٥٦", "456"),
        ("12", "12"),
    ],
)
def test_en_digits(text, expected):
    assert en_digits(text) == expected


def test_fa_digits_and_normalize():
    assert fa_digits("2026") == "۲۰۲۶"
    assert normalize("علي  كريم") == "علی کریم"


@pytest.mark.parametrize(
    ("token", "seconds"),
    [
        ("30s", 30),
        ("10m", 600),
        ("2h", 7200),
        ("1d", 86400),
        ("1w", 604800),
        ("۱۰ دقیقه", 600),
        ("۵روز", 5 * 86400),
    ],
)
def test_parse_duration(token, seconds):
    found, value = parse_duration(token)
    assert found and value == seconds


def test_parse_permanent_duration():
    assert parse_duration("دائمی") == (True, None)
    assert parse_duration("permanent") == (True, None)
    assert parse_duration("سلام") == (False, None)


def test_duration_bounds():
    with pytest.raises(DurationTooShort):
        validate_duration(10)
    with pytest.raises(DurationTooLong):
        validate_duration(400 * 86400)
    validate_duration(None)
    validate_duration(30)


def test_duration_label():
    assert duration_label(None) is None
    assert duration_label(600) == "۱۰ دقیقه"
    assert duration_label(3600) == "۱ ساعت"
    assert duration_label(86400 + 7200) == "۱ روز و ۲ ساعت"


def test_parse_slash_command_with_target_and_duration():
    parsed = parse_command("/ban 123456789 2h تبلیغات")
    assert parsed is not None
    assert parsed.name == "ban" and not parsed.is_alias
    assert parsed.args.target == "123456789"
    assert parsed.args.duration == 7200
    assert parsed.args.reason == "تبلیغات"


def test_parse_command_with_bot_mention():
    parsed = parse_command("/mute@HelliBot 10m")
    assert parsed is not None and parsed.name == "mute" and parsed.args.duration == 600


def test_parse_persian_alias_prefers_longest_match():
    parsed = parse_command("رفع مسدودی")
    assert parsed is not None and parsed.name == "unban" and parsed.is_alias

    parsed = parse_command("آمار شبانه روشن")
    assert parsed is not None and parsed.name == "dailystats" and parsed.args.reason == "روشن"


def test_parse_reason_only():
    parsed = parse_command("/warn 3 بار تبلیغ")
    assert parsed is not None
    assert parsed.args.target is None and parsed.args.reason == "3 بار تبلیغ"


def test_unknown_command_is_ignored():
    assert parse_command("/unknown") is None
    assert parse_command("سلام دوستان") is None


def test_persian_digits_target():
    parsed = parse_command("/ban ۱۲۳۴۵۶۷۸۹")
    assert parsed is not None and parsed.args.target == "123456789"


def test_jalali_conversion():
    assert gregorian_to_jalali(date(2026, 11, 7)) == (1405, 8, 16)
    assert gregorian_to_jalali(date(2025, 3, 21)) == (1404, 1, 1)
    assert jalali_date(date(2026, 3, 21)) == "۱۴۰۵/۰۱/۰۱"


def test_tehran_day_shifts_near_midnight():
    # 20:30 UTC = 00:00 تهران (UTC+3:30)
    assert tehran_day(datetime(2026, 11, 7, 20, 30)) == date(2026, 11, 8)
    assert tehran_day(datetime(2026, 11, 7, 19, 0)) == date(2026, 11, 7)


def test_format_datetime_uses_tehran_time():
    assert format_datetime(datetime(2026, 11, 7, 11, 0)) == "۱۴۰۵/۰۸/۱۶ ۱۴:۳۰"
