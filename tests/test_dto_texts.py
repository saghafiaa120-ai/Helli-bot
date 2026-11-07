from core import texts_fa
from domain.dto import BotStatus


def test_bot_status_not_admin_reports_only_is_admin():
    assert BotStatus().missing_permissions == ("is_admin",)


def test_bot_status_admin_missing_one_permission():
    status = BotStatus(is_admin=True, can_delete_messages=True, can_restrict_members=False)
    assert status.missing_permissions == ("can_restrict_members",)


def test_bot_status_complete():
    status = BotStatus(is_admin=True, can_delete_messages=True, can_restrict_members=True)
    assert status.missing_permissions == ()


def test_registered_text_when_permissions_complete():
    text = texts_fa.group_registered("گروه من", ())
    assert "گروه من" in text
    assert "⚠️" not in text


def test_registered_text_lists_needed_permissions_when_not_admin():
    text = texts_fa.group_registered("گروه من", ("is_admin",))
    assert "⚠️" in text
    assert "حذف پیام‌ها" in text
    assert "محدود کردن کاربران" in text


def test_registered_text_lists_only_missing_permission():
    text = texts_fa.group_registered(None, ("can_restrict_members",))
    assert "محدود کردن کاربران" in text
    assert "حذف پیام‌ها" not in text


def test_group_title_is_html_escaped():
    text = texts_fa.group_registered("<b>x</b>", ())
    assert "<b>x</b>" not in text
    assert "&lt;b&gt;x&lt;/b&gt;" in text


def test_help_lists_only_real_commands():
    """هر دستوری که در راهنما آمده باید واقعاً پیاده‌سازی شده باشد (بدون دستور نمایشی)."""
    import re

    from domain.commands import SLASH_COMMANDS

    text = texts_fa.help_text()
    listed = set(re.findall(r"(?<![<\w])/([a-z]+)", text))
    assert {"start", "help", "ban", "mute", "stats", "panel"} <= listed
    assert listed <= {"start", "help"} | set(SLASH_COMMANDS)
    for not_yet in ("rules", "filter", "lock", "unlock", "report"):
        assert f"/{not_yet}" not in text


def test_every_group_command_is_real():
    from domain.commands import SLASH_COMMANDS

    for name, _ in texts_fa.GROUP_COMMANDS:
        assert name in {"start", "help"} or name in SLASH_COMMANDS


def test_number_formatting():
    assert texts_fa.fa_number(1234567) == "۱٬۲۳۴٬۵۶۷"
    assert texts_fa.fa_number(5) == "۵"


def test_daily_report_text():
    text = texts_fa.daily_report("۱۴۰۵/۰۸/۱۶", 1500, 3, [("علی", 900), ("<b>x</b>", 400), ("c", 200), ("d", 50)])
    assert "۱٬۵۰۰ پیام از ۳ نفر" in text
    assert "🥇 علی — ۹۰۰ پیام" in text and "🥉" in text and "۴. d" in text
    assert "<b>x</b>" not in text.split("فعال‌ترین‌ها")[1]  # نام کاربران escape می‌شود


def test_help_sections_mention_only_real_commands():
    """هر بخش راهنما فقط دستورهایی را نشان دهد که واقعاً وجود دارند."""
    import re

    from domain.commands import SLASH_COMMANDS

    allowed = {"start", "help"} | set(SLASH_COMMANDS)
    for key, _label in texts_fa.HELP_SECTIONS:
        text = texts_fa.help_section(key)
        listed = set(re.findall(r"(?<![<\w])/([a-z]+)", text))
        assert listed <= allowed, (key, listed - allowed)


def test_help_sections_are_short_enough_for_telegram():
    for key, _label in texts_fa.HELP_SECTIONS:
        assert 0 < len(texts_fa.help_section(key)) < 2000


def test_help_unknown_section_falls_back_to_main():
    assert texts_fa.help_section("nope") == texts_fa.help_text()


def test_help_main_mentions_panel_and_core_commands():
    text = texts_fa.help_text()
    for command in ("/start", "/help", "/panel", "/ban", "/mute", "/stats"):
        assert command in text


def test_help_sections_are_well_formed_html():
    """تگ‌های باز و بسته باید جفت باشند؛ تلگرام HTML ناقص را رد می‌کند."""
    import re

    texts = [texts_fa.help_text()] + [
        texts_fa.help_section(key) for key, _ in texts_fa.HELP_SECTIONS
    ]
    for text in texts:
        for tag in ("b", "i", "code", "blockquote"):
            opened = len(re.findall(rf"<{tag}>", text))
            closed = len(re.findall(rf"</{tag}>", text))
            assert opened == closed, (tag, opened, closed)
