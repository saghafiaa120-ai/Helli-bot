"""دکمه‌های راهنمای بخش‌بندی‌شده."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core import texts_fa

BTN_HELP_BACK = "↩️ بازگشت"
BTN_HELP_CLOSE = "❌ بستن"


def help_keyboard(active: str = "main") -> InlineKeyboardMarkup:
    """دکمه بخش‌ها (دو ستون)؛ در بخش‌های داخلی، دکمه بازگشت هم اضافه می‌شود."""
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"help:{key}")
        for key, label in texts_fa.HELP_SECTIONS
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    if active != "main":
        rows.append([InlineKeyboardButton(text=BTN_HELP_BACK, callback_data="help:main")])
    rows.append([InlineKeyboardButton(text=BTN_HELP_CLOSE, callback_data="help:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
