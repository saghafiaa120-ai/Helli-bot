"""دکمه‌های شیشه‌ای بازی‌ها (دوز، اسپای، مافیا).

قالب `callback_data`:
- `xo:move:<خانه>` / `xo:accept` / `xo:decline` / `xo:new` / `xo:close`
- `spy:join` / `spy:leave` / `spy:start` / `spy:cancel` / `spy:votestart`
  / `spy:vote:<id>` / `spy:endvote` / `spy:guess:<شماره مکان>`
- `mafia:join` / `mafia:leave` / `mafia:start` / `mafia:cancel` / `mafia:endnight`
  / `mafia:kill:<id>` / `mafia:save:<id>` / `mafia:check:<id>`
  / `mafia:vote:<id>` / `mafia:endvote`
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core import texts_games_fa as texts
from services.games.spyfall import LOCATIONS
from services.games.xo import XOGame


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _rows_of(buttons: list[InlineKeyboardButton], per_row: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[index : index + per_row] for index in range(0, len(buttons), per_row)]


# ----- دوز --------------------------------------------------------------------------


def xo_invite_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_ACCEPT, "xo:accept"), _button(texts.BTN_DECLINE, "xo:decline")]
        ]
    )


def xo_keyboard(game: XOGame) -> InlineKeyboardMarkup:
    if game.finished:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [_button(texts.BTN_NEW, "xo:new"), _button(texts.BTN_CLOSE, "xo:close")]
            ]
        )
    rows = [
        [
            _button(
                texts.XO_MARKS.get(game.board[row * 3 + col], texts.EMPTY_CELL),
                f"xo:move:{row * 3 + col}",
            )
            for col in range(3)
        ]
        for row in range(3)
    ]
    rows.append([_button(texts.BTN_CLOSE, "xo:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ----- اسپای ------------------------------------------------------------------------


def spy_lobby_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_JOIN, "spy:join"), _button(texts.BTN_LEAVE, "spy:leave")],
            [_button(texts.BTN_START, "spy:start"), _button(texts.BTN_CANCEL, "spy:cancel")],
        ]
    )


def spy_play_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("🗳 رأی‌گیری", "spy:votestart")],
            [_button(texts.BTN_CANCEL, "spy:cancel")],
        ]
    )


def spy_vote_keyboard(players: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """players: فهرست (شناسه، نام)."""
    buttons = [_button(f"❓ {name}"[:40], f"spy:vote:{user_id}") for user_id, name in players]
    rows = _rows_of(buttons)
    rows.append([_button("📊 پایان رأی‌گیری", "spy:endvote")])
    rows.append([_button(texts.BTN_CANCEL, "spy:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def spy_guess_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        _button(f"📍 {name}"[:40], f"spy:guess:{index}")
        for index, name in enumerate(LOCATIONS)
    ]
    return InlineKeyboardMarkup(inline_keyboard=_rows_of(buttons))


# ----- مافیا ------------------------------------------------------------------------


def mafia_lobby_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_JOIN, "mafia:join"), _button(texts.BTN_LEAVE, "mafia:leave")],
            [_button(texts.BTN_START, "mafia:start"), _button(texts.BTN_CANCEL, "mafia:cancel")],
        ]
    )


def mafia_night_keyboard(action: str, targets: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """action: kill | save | check."""
    buttons = [_button(f"🎯 {name}"[:40], f"mafia:{action}:{user_id}") for user_id, name in targets]
    rows = _rows_of(buttons)
    rows.append([_button("⏭ رد کردن", f"mafia:{action}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mafia_day_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("🗳 رأی‌گیری", "mafia:voteopen")],
            [_button(texts.BTN_CANCEL, "mafia:cancel")],
        ]
    )


def mafia_vote_keyboard(players: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = [_button(f"❓ {name}"[:40], f"mafia:vote:{user_id}") for user_id, name in players]
    rows = _rows_of(buttons)
    rows.append([_button("📊 پایان رأی‌گیری", "mafia:endvote")])
    rows.append([_button(texts.BTN_CANCEL, "mafia:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mafia_night_control_keyboard() -> InlineKeyboardMarkup:
    """دکمه‌های گروه در شب: پایان شب (سازنده) و لغو."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("🌅 پایان شب", "mafia:endnight")],
            [_button(texts.BTN_CANCEL, "mafia:cancel")],
        ]
    )


def new_game_keyboard(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(texts.BTN_NEW, f"{kind}:new"), _button(texts.BTN_CLOSE, f"{kind}:close")]]
    )
