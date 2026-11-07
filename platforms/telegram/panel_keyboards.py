"""دکمه‌های شیشه‌ای پنل کاربری و تأییدیه‌ها."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core import texts_fa
from core.textnorm import fa_digits

# صفحه‌بندی فهرست گروه‌ها
GROUPS_PAGE_SIZE = 6


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(texts_fa.BTN_CONFIRM, f"confirm:yes:{token}"),
                _button(texts_fa.BTN_CANCEL, f"confirm:no:{token}"),
            ]
        ]
    )


def group_panel_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(texts_fa.BTN_PANEL_STATS, f"panel:stats:{group_id}"),
                _button(texts_fa.BTN_PANEL_ME, "panel:me"),
            ],
            [
                _button(texts_fa.BTN_PANEL_SETTINGS, f"panel:settings:{group_id}"),
                _button(texts_fa.BTN_PANEL_HELP, "panel:help"),
            ],
            [
                _button(texts_fa.BTN_PANEL_REFRESH, f"panel:group:{group_id}"),
                _button(texts_fa.BTN_PANEL_CLOSE, "panel:close"),
            ],
        ]
    )


def private_panel_keyboard(has_groups: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            _button(texts_fa.BTN_PANEL_MY_GROUPS, "panel:groups:1"),
            _button(texts_fa.BTN_PANEL_HELP, "panel:help"),
        ]
    ]
    if not has_groups:
        rows[0] = [_button(texts_fa.BTN_PANEL_HELP, "panel:help")]
    rows.append([_button(texts_fa.BTN_PANEL_CLOSE, "panel:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def groups_keyboard(
    groups: list[tuple[int, str | None, int]], page: int, pages: int
) -> InlineKeyboardMarkup:
    """groups: فهرست (شناسه داخلی، عنوان، شناسه خارجی)."""
    rows = [
        [
            _button(
                texts_fa.panel_group_button(title, external_id),
                f"panel:group:{group_id}",
            )
        ]
        for group_id, title, external_id in groups
    ]
    navigation = []
    if page > 1:
        navigation.append(_button("◀️ قبلی", f"panel:groups:{page - 1}"))
    if page < pages:
        navigation.append(_button("بعدی ▶️", f"panel:groups:{page + 1}"))
    if navigation:
        rows.append(navigation)
    rows.append([_button(texts_fa.BTN_PANEL_BACK, "panel:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_detail_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """نمای یک گروه از داخل گفتگوی خصوصی."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(texts_fa.BTN_PANEL_STATS, f"panel:stats:{group_id}"),
                _button(texts_fa.BTN_PANEL_SETTINGS, f"panel:settings:{group_id}"),
            ],
            [
                _button(texts_fa.BTN_PANEL_REFRESH, f"panel:group:{group_id}"),
                _button(texts_fa.BTN_PANEL_BACK, "panel:groups:1"),
            ],
        ]
    )


def settings_keyboard(
    group_id: int,
    *,
    daily_report: bool,
    warn_limit: int,
    warn_mute_label: str | None,
    confirm_sensitive: bool,
) -> InlineKeyboardMarkup:
    limit = fa_digits(str(warn_limit)) if warn_limit else "بدون سقف"
    rows = [
        [
            _button(
                f"{texts_fa.BTN_SETTING_DAILY}: {'روشن' if daily_report else 'خاموش'}",
                f"panel:toggle:{group_id}:daily",
            )
        ],
        [_button(f"{texts_fa.BTN_SETTING_WARN_LIMIT}: {limit}", f"panel:toggle:{group_id}:warnlimit")],
        [
            _button(
                f"{texts_fa.BTN_SETTING_WARN_MUTE}: {warn_mute_label or 'دائمی'}",
                f"panel:toggle:{group_id}:warnmute",
            )
        ],
        [
            _button(
                f"{texts_fa.BTN_SETTING_CONFIRM}: {'روشن' if confirm_sensitive else 'خاموش'}",
                f"panel:toggle:{group_id}:confirm",
            )
        ],
    ]
    back = f"panel:group:{group_id}"
    rows.append([_button(texts_fa.BTN_PANEL_BACK, back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard(group_id: int | None) -> InlineKeyboardMarkup:
    target = f"panel:group:{group_id}" if group_id is not None else "panel:home"
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(texts_fa.BTN_PANEL_BACK, target)]]
    )
