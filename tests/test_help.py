"""تست دکمه‌های راهنما."""

from __future__ import annotations

import pytest

pytest.importorskip("aiogram")

from core import texts_fa
from platforms.telegram.help_keyboards import help_keyboard


def _datas(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_main_keyboard_has_every_section_and_close():
    datas = _datas(help_keyboard("main"))
    for key, _label in texts_fa.HELP_SECTIONS:
        assert f"help:{key}" in datas
    assert datas[-1] == "help:close"
    assert "help:main" not in datas


def test_section_keyboard_has_back_button():
    datas = _datas(help_keyboard("users"))
    assert "help:main" in datas
    assert datas[-1] == "help:close"


def test_section_buttons_are_two_per_row():
    rows = help_keyboard("main").inline_keyboard
    assert len(rows[0]) == 2
    assert len(rows[1]) == 2
    assert len(rows[-1]) == 1  # فقط دکمه بستن


def test_every_section_label_is_short_enough():
    for _key, label in texts_fa.HELP_SECTIONS:
        assert len(label) <= 24
