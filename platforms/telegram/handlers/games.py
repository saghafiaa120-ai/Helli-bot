"""دستورها و دکمه‌های بازی‌ها: دوز (XO)، اسپای و مافیا.

منطق هر بازی در `services/games/` است؛ این ماژول فقط پیام‌ها را می‌فرستد و
دکمه‌ها را به متدهای بازی وصل می‌کند. نقش‌ها و انتخاب‌های شب با پیام خصوصی
فرستاده می‌شوند، پس هر بازیکن باید یک بار ربات را در پیام خصوصی `/start` کند.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core import texts_fa
from core import texts_games_fa as gtexts
from core.config import Settings
from domain.commands import ParsedCommand
from platforms.base import PlatformAdapter
from platforms.telegram import game_keyboards as kb
from platforms.telegram import ui
from platforms.telegram.filters import TextCommand
from platforms.telegram.guards import (
    TargetError,
    load_group_context,
    resolve_target,
)
from platforms.telegram.mapping import GROUP_CHAT_TYPES
from platforms.telegram.resilience import with_retry
from services.games.base import GameError, GameRegistry
from services.games.mafia import (
    PHASE_NIGHT,
    PHASE_VOTE,
    ROLE_DETECTIVE,
    ROLE_DOCTOR,
    ROLE_MAFIA,
    MafiaGame,
)
from services.games.spyfall import LOCATIONS, SpyfallGame
from services.games.xo import XOGame

logger = logging.getLogger(__name__)

GAME_LABELS = {"xo": "دوز", "spy": "اسپای", "mafia": "مافیا"}


def _display(tg_user: object) -> str:
    first = getattr(tg_user, "first_name", None)
    last = getattr(tg_user, "last_name", None)
    username = getattr(tg_user, "username", None)
    user_id = int(getattr(tg_user, "external_id", None) or getattr(tg_user, "id", 0))
    return texts_fa.display_name(first, last, username, user_id)


async def _dm(bot: Bot, user_id: int, text: str, markup: InlineKeyboardMarkup | None = None) -> bool:
    """پیام خصوصی می‌فرستد؛ اگر کاربر ربات را استارت نکرده باشد False برمی‌گرداند."""
    try:
        await bot.send_message(user_id, text, reply_markup=markup)
        return True
    except Exception as exc:
        logger.info("Could not DM user %s: %s", user_id, exc)
        return False


async def _say(
    bot: Bot, chat_id: int, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    try:
        await bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as exc:
        logger.warning("Could not send game message to %s: %s", chat_id, exc)


def _error(kind: str) -> str:
    return gtexts.error_text(kind)


# ----- دستور بازی -------------------------------------------------------------------


async def on_game_command(
    message: Message,
    parsed: ParsedCommand,
    session: AsyncSession,
    adapter: PlatformAdapter,
    config: Settings,
    games: GameRegistry,
) -> None:
    if message.from_user is None:
        return

    if parsed.name == "stopgame":
        await _stop_game(message, session, config, games)
        return

    if message.chat.type not in GROUP_CHAT_TYPES:
        await message.answer(gtexts.only_group())
        return

    active = games.get(message.chat.id)
    if active is not None and active.is_finished():
        # بازی تمام‌شده جلوی شروع بازی تازه را نمی‌گیرد.
        games.drop(message.chat.id, active)
        active = None
    if active is not None:
        await message.answer(gtexts.busy(GAME_LABELS.get(active.kind, active.kind)))
        return

    if parsed.name == "xo":
        await _start_xo(message, parsed, session, adapter, games)
    elif parsed.name == "spy":
        await _start_spy(message, games)
    elif parsed.name == "mafia":
        await _start_mafia(message, games)


async def _stop_game(
    message: Message, session: AsyncSession, config: Settings, games: GameRegistry
) -> None:
    game = games.get(message.chat.id)
    if game is None:
        await message.answer("ℹ️ بازی فعالی در این گروه نیست.")
        return

    allowed = message.from_user is not None and message.from_user.id == game.host_id
    if not allowed:
        ctx = await load_group_context(message, session, config, require_admin=False)
        if ctx is None:
            return
        allowed = ctx.actor.role is not None or ctx.actor.is_global_owner
    if not allowed:
        await message.answer(gtexts.only_host())
        return

    games.drop(message.chat.id, game)
    await message.answer(gtexts.stopped())


# ----- دوز --------------------------------------------------------------------------


async def _start_xo(
    message: Message,
    parsed: ParsedCommand,
    session: AsyncSession,
    adapter: PlatformAdapter,
    games: GameRegistry,
) -> None:
    sender = message.from_user
    assert sender is not None

    opponent_id: int | None = None
    opponent_name = ""

    replied = message.reply_to_message
    if replied is not None and replied.from_user is not None and not replied.from_user.is_bot:
        opponent_id = replied.from_user.id
        opponent_name = _display(replied.from_user)
    elif parsed.args.target:
        try:
            user = await resolve_target(message, session, parsed.args)
        except TargetError as exc:
            if exc.kind == "no_target":
                await message.answer(texts_fa.usage("info"))
            else:
                await message.answer(texts_fa.moderation_error(exc.kind, name=exc.value))
            return
        if user.external_id != sender.id:
            opponent_id = user.external_id
            opponent_name = _display(user)

    if opponent_id is None:
        game = XOGame(
            message.chat.id,
            sender.id,
            _display(sender),
            mode="bot",
            opponent_id=adapter.bot_user_id,
        )
        game.start()
        games.set(message.chat.id, game)
        await message.answer(
            gtexts.xo_started(game.host_name, "ربات", vs_bot=True),
            reply_markup=kb.xo_keyboard(game),
        )
        return

    game = XOGame(
        message.chat.id,
        sender.id,
        _display(sender),
        mode="duel",
        opponent_id=opponent_id,
        opponent_name=opponent_name,
    )
    games.set(message.chat.id, game)
    await message.answer(
        gtexts.xo_invite(game.host_name, opponent_name),
        reply_markup=kb.xo_invite_keyboard(),
    )


def _xo_text(game: XOGame) -> str:
    return gtexts.xo_board(
        first=game.host_name,
        second=game.opponent_name,
        turn=game.name_of(game.turn),
        winner=game.winner,
        vs_bot=game.vs_bot,
    )


async def _xo_callback(
    callback: CallbackQuery, game: XOGame, games: GameRegistry
) -> None:
    data = (callback.data or "").split(":")
    action = data[1] if len(data) > 1 else ""
    user = callback.from_user

    if action == "close":
        games.drop(game.chat_id, game)
        await _close_message(callback)
        return

    if user is None:
        await ui.answer(callback)
        return

    if action == "accept":
        if not game.awaiting_accept:
            await ui.answer(callback, gtexts.finished(), alert=True)
            return
        if user.id != game.opponent_id:
            await ui.answer(callback, gtexts.xo_only_opponent(), alert=True)
            return
        game.start()
        await _edit(callback, gtexts.xo_started(game.host_name, game.opponent_name, vs_bot=False), kb.xo_keyboard(game))
        return

    if action == "decline":
        if user.id != game.opponent_id:
            await ui.answer(callback, gtexts.xo_only_opponent(), alert=True)
            return
        games.drop(game.chat_id, game)
        await _edit(callback, gtexts.xo_declined(game.opponent_name), None)
        return

    if action == "new":
        if not game.has_player(user.id):
            await ui.answer(callback, gtexts.not_player(), alert=True)
            return
        game.reset()
        await _edit(callback, gtexts.xo_started(game.host_name, game.opponent_name, vs_bot=game.vs_bot), kb.xo_keyboard(game))
        return

    if action == "move":
        try:
            index = int(data[2])
            game.play(user.id, index)
        except (IndexError, ValueError):
            await ui.answer(callback, _error("bad_target"), alert=True)
            return
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        if game.vs_bot and not game.finished:
            game.bot_turn()
        await _edit(callback, _xo_text(game), kb.xo_keyboard(game))
        return

    await ui.answer(callback)


# ----- اسپای ------------------------------------------------------------------------


async def _start_spy(message: Message, games: GameRegistry) -> None:
    sender = message.from_user
    assert sender is not None
    game = SpyfallGame(message.chat.id, sender.id, _display(sender))
    game.add_player(sender.id, _display(sender))
    games.set(message.chat.id, game)
    await message.answer(
        gtexts.spy_lobby(game.host_name, game.names, SpyfallGame.MIN_PLAYERS, SpyfallGame.MAX_PLAYERS),
        reply_markup=kb.spy_lobby_keyboard(),
    )


def _spy_lobby_text(game: SpyfallGame) -> str:
    return gtexts.spy_lobby(
        game.host_name, game.names, SpyfallGame.MIN_PLAYERS, SpyfallGame.MAX_PLAYERS
    )


async def _spy_callback(
    callback: CallbackQuery, game: SpyfallGame, games: GameRegistry, bot: Bot
) -> None:
    data = (callback.data or "").split(":")
    action = data[1] if len(data) > 1 else ""
    user = callback.from_user

    if action == "close":
        games.drop(game.chat_id, game)
        await _close_message(callback)
        return

    if action == "new":
        fresh = SpyfallGame(game.chat_id, game.host_id, game.host_name)
        fresh.add_player(game.host_id, game.host_name)
        games.set(game.chat_id, fresh)
        await _edit(callback, _spy_lobby_text(fresh), kb.spy_lobby_keyboard())
        return

    if action == "cancel":
        games.drop(game.chat_id, game)
        await _edit(callback, gtexts.stopped(), None)
        return

    if user is None:
        await ui.answer(callback)
        return

    if action in ("join", "leave"):
        try:
            if action == "join":
                game.add_player(user.id, _display(user))
            else:
                game.remove_player(user.id)
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        await _edit(callback, _spy_lobby_text(game), kb.spy_lobby_keyboard())
        return

    if action == "start":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        try:
            game.start()
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        failed = await _send_spy_roles(bot, game)
        if failed:
            game.reset_to_lobby()
            await _edit(
                callback,
                gtexts.dm_failed(failed) + "\n\n" + _spy_lobby_text(game),
                kb.spy_lobby_keyboard(),
            )
            return
        text = gtexts.spy_started(len(game.players)) + "\n\n" + gtexts.spy_locations(LOCATIONS)
        await _edit(callback, text, kb.spy_play_keyboard())
        return

    if action == "votestart":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        try:
            game.begin_vote()
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        await _edit(
            callback,
            gtexts.spy_vote_opened(),
            kb.spy_vote_keyboard([(p.user_id, p.name) for p in game.players]),
        )
        return

    if action == "vote":
        try:
            target_id = int(data[2])
            game.cast_vote(user.id, target_id)
        except (IndexError, ValueError):
            await ui.answer(callback, _error("bad_target"), alert=True)
            return
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        await ui.answer(callback, gtexts.spy_voted(_display(user)))
        return

    if action == "endvote":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        try:
            outcome, accused_id = game.resolve_vote()
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        if outcome == "tie":
            await _edit(
                callback,
                gtexts.spy_tie(),
                kb.spy_vote_keyboard([(p.user_id, p.name) for p in game.players]),
            )
            return
        text = _spy_result_text(game, outcome, accused_id)
        await _edit(callback, text, kb.new_game_keyboard("spy"))
        return

    if action == "guess":
        try:
            index = int(data[2])
            correct = game.guess(user.id, index)
        except (IndexError, ValueError):
            await ui.answer(callback, _error("bad_target"), alert=True)
            return
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        spy = game.player(game.spy_id) if game.spy_id else None
        spy_name = spy.name if spy else "جاسوس"
        text = (
            gtexts.spy_guess_correct(spy_name, game.location or "")
            if correct
            else gtexts.spy_guess_wrong(spy_name, game.location or "")
        )
        await _edit(callback, text, None)
        await _say(bot, game.chat_id, text, kb.new_game_keyboard("spy"))
        return

    await ui.answer(callback)


def _spy_result_text(game: SpyfallGame, outcome: str, accused_id: int | None) -> str:
    spy = game.player(game.spy_id) if game.spy_id else None
    accused = game.player(accused_id) if accused_id else None
    spy_name = spy.name if spy else "جاسوس"
    location = game.location or ""
    if outcome == "spy":
        return gtexts.spy_result_caught(spy_name, location)
    return gtexts.spy_result_wrong(accused.name if accused else "—", spy_name, location)


async def _send_spy_roles(bot: Bot, game: SpyfallGame) -> list[str]:
    """نقش هر بازیکن را در پیام خصوصی می‌فرستد؛ نام ناموفق‌ها را برمی‌گرداند."""
    failed: list[str] = []
    for player in game.players:
        if player.user_id == game.spy_id:
            sent = await _dm(
                bot, player.user_id, gtexts.spy_role_spy(), kb.spy_guess_keyboard()
            )
        else:
            sent = await _dm(bot, player.user_id, gtexts.spy_role_citizen(game.location or ""))
        if not sent:
            failed.append(player.name)
    return failed


# ----- مافیا ------------------------------------------------------------------------


async def _start_mafia(message: Message, games: GameRegistry) -> None:
    sender = message.from_user
    assert sender is not None
    game = MafiaGame(message.chat.id, sender.id, _display(sender))
    game.add_player(sender.id, _display(sender))
    games.set(message.chat.id, game)
    await message.answer(
        gtexts.mafia_lobby(
            game.host_name, game.names, MafiaGame.MIN_PLAYERS, MafiaGame.MAX_PLAYERS
        ),
        reply_markup=kb.mafia_lobby_keyboard(),
    )


def _mafia_lobby_text(game: MafiaGame) -> str:
    return gtexts.mafia_lobby(
        game.host_name, game.names, MafiaGame.MIN_PLAYERS, MafiaGame.MAX_PLAYERS
    )


async def _mafia_callback(
    callback: CallbackQuery, game: MafiaGame, games: GameRegistry, bot: Bot
) -> None:
    data = (callback.data or "").split(":")
    action = data[1] if len(data) > 1 else ""
    user = callback.from_user

    if action == "close":
        games.drop(game.chat_id, game)
        await _close_message(callback)
        return

    if action == "new":
        fresh = MafiaGame(game.chat_id, game.host_id, game.host_name)
        fresh.add_player(game.host_id, game.host_name)
        games.set(game.chat_id, fresh)
        await _edit(callback, _mafia_lobby_text(fresh), kb.mafia_lobby_keyboard())
        return

    if action == "cancel":
        games.drop(game.chat_id, game)
        await _edit(callback, gtexts.stopped(), None)
        return

    if user is None:
        await ui.answer(callback)
        return

    if action in ("join", "leave"):
        try:
            if action == "join":
                game.add_player(user.id, _display(user))
            else:
                game.remove_player(user.id)
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        await _edit(callback, _mafia_lobby_text(game), kb.mafia_lobby_keyboard())
        return

    if action == "start":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        try:
            game.start()
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        failed = await _send_mafia_roles(bot, game)
        if failed:
            games.drop(game.chat_id, game)
            await _edit(callback, gtexts.dm_failed(failed), None)
            return
        await _edit(callback, gtexts.mafia_started(len(game.players)), None)
        await _mafia_open_night(bot, game)
        return

    if action == "endnight":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        if game.phase != PHASE_NIGHT:
            await ui.answer(callback, "🌙 الان شب نیست.", alert=True)
            return
        await ui.answer(callback)
        await _mafia_resolve_night(bot, game)
        return

    if action in ("kill", "save", "check"):
        await _mafia_night_action(callback, game, games, bot, action, data)
        return

    if action == "voteopen":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        try:
            game.begin_vote()
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        await _edit(
            callback,
            gtexts.mafia_vote_opened(),
            kb.mafia_vote_keyboard([(p.user_id, p.name) for p in game.alive_players()]),
        )
        return

    if action == "vote":
        try:
            target_id = int(data[2])
            game.cast_vote(user.id, target_id)
        except (IndexError, ValueError):
            await ui.answer(callback, _error("bad_target"), alert=True)
            return
        except GameError as exc:
            await ui.answer(callback, _error(exc.kind), alert=True)
            return
        await ui.answer(callback, gtexts.mafia_voted(_display(user)))
        return

    if action == "endvote":
        if user.id != game.host_id:
            await ui.answer(callback, gtexts.only_host(), alert=True)
            return
        if game.phase != PHASE_VOTE:
            await ui.answer(callback, "🗳 الان مرحله رأی‌گیری نیست.", alert=True)
            return
        eliminated = game.resolve_vote()
        lines = [
            gtexts.mafia_vote_result(
                eliminated.name if eliminated else None,
                eliminated.role if eliminated else None,
            )
        ]
        winner = game.winner_side()
        if winner is not None:
            game.finish(winner)
            lines.append("")
            lines.append(gtexts.mafia_end(winner, game.reveal()))
            await _edit(callback, "\n".join(lines), kb.new_game_keyboard("mafia"))
            return
        await _edit(callback, "\n".join(lines), None)
        await _mafia_open_night(bot, game)
        return

    await ui.answer(callback)


async def _mafia_night_action(
    callback: CallbackQuery,
    game: MafiaGame,
    games: GameRegistry,
    bot: Bot,
    action: str,
    data: list[str],
) -> None:
    user = callback.from_user
    assert user is not None
    try:
        target_id = int(data[2])
    except (IndexError, ValueError):
        await ui.answer(callback, _error("bad_target"), alert=True)
        return
    target_id = target_id or None  # دکمه «رد کردن» شناسه 0 دارد

    try:
        if action == "kill":
            game.submit_kill(user.id, target_id)
            await ui.safe_edit(callback.message, "🔪 انتخاب شما ثبت شد. منتظر بقیه بمانید.")
        elif action == "save":
            game.submit_save(user.id, target_id)
            await ui.safe_edit(callback.message, "🩺 انتخاب شما ثبت شد. منتظر بقیه بمانید.")
        else:
            if target_id is None:
                await ui.answer(callback, "⚠️ برای استعلام یک نفر را انتخاب کنید.", alert=True)
                return
            is_mafia = game.submit_check(user.id, target_id)
            target = game.player(target_id)
            await ui.safe_edit(
                callback.message,
                gtexts.mafia_detective_result(target.name if target else "—", is_mafia),
            )
    except GameError as exc:
        await ui.answer(callback, _error(exc.kind), alert=True)
        return

    await ui.answer(callback)
    if game.night_ready():
        await _mafia_resolve_night(bot, game)


async def _send_mafia_roles(bot: Bot, game: MafiaGame) -> list[str]:
    failed: list[str] = []
    for player in game.players:
        if player.role == ROLE_MAFIA:
            text = gtexts.mafia_role_mafia(game.teammates_of(player.user_id))
        elif player.role == ROLE_DOCTOR:
            text = gtexts.mafia_role_doctor()
        elif player.role == ROLE_DETECTIVE:
            text = gtexts.mafia_role_detective()
        else:
            text = gtexts.mafia_role_citizen()
        if not await _dm(bot, player.user_id, text):
            failed.append(player.name)
    return failed


async def _mafia_open_night(bot: Bot, game: MafiaGame) -> None:
    game.begin_night()
    for player in game.alive_players():
        if player.role == ROLE_MAFIA:
            targets = [(p.user_id, p.name) for p in game.targets_alive(exclude_mafia=True)]
            await _dm(
                bot,
                player.user_id,
                gtexts.mafia_night_mafia_prompt([name for _, name in targets]),
                kb.mafia_night_keyboard("kill", targets),
            )
        elif player.role == ROLE_DOCTOR:
            targets = [(p.user_id, p.name) for p in game.targets_alive()]
            await _dm(
                bot,
                player.user_id,
                gtexts.mafia_night_doctor_prompt([name for _, name in targets]),
                kb.mafia_night_keyboard("save", targets),
            )
        elif player.role == ROLE_DETECTIVE:
            targets = [
                (p.user_id, p.name)
                for p in game.targets_alive(exclude_id=player.user_id)
            ]
            await _dm(
                bot,
                player.user_id,
                gtexts.mafia_night_detective_prompt([name for _, name in targets]),
                kb.mafia_night_keyboard("check", targets),
            )
    await _say(
        bot,
        game.chat_id,
        gtexts.mafia_night(game.night_number),
        kb.mafia_night_control_keyboard(),
    )


async def _mafia_resolve_night(bot: Bot, game: MafiaGame) -> None:
    if game.phase != PHASE_NIGHT:
        return
    result = game.resolve_night()
    lines = [
        gtexts.mafia_day(
            game.night_number,
            result.killed.name if result.killed else None,
            result.killed.role if result.killed else None,
            result.saved,
        )
    ]
    winner = game.winner_side()
    if winner is not None:
        game.finish(winner)
        lines.append("")
        lines.append(gtexts.mafia_end(winner, game.reveal()))
        await _say(bot, game.chat_id, "\n".join(lines), kb.new_game_keyboard("mafia"))
        return
    await _say(bot, game.chat_id, "\n".join(lines), kb.mafia_day_keyboard())


# ----- دکمه‌های مشترک ---------------------------------------------------------------


async def _edit(
    callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None
) -> None:
    await ui.safe_edit(callback.message, text, reply_markup=markup, fallback_send=True)
    await ui.answer(callback)


async def _close_message(callback: CallbackQuery) -> None:
    message = callback.message
    if message is not None:
        try:
            await with_retry(lambda: message.delete(), what="game delete")
        except Exception:
            await ui.safe_edit(message, "🎮 بازی بسته شد.")
    await ui.answer(callback)


# ----- روتر -------------------------------------------------------------------------


async def on_game_callback(
    callback: CallbackQuery, games: GameRegistry, bot: Bot
) -> None:
    data = (callback.data or "").split(":")
    namespace = data[0] if data else ""
    chat_id = callback.message.chat.id if callback.message is not None else None

    game = games.get(chat_id) if chat_id is not None else None
    if game is None and callback.from_user is not None:
        # دکمه‌های پیام خصوصی (نقش‌ها و انتخاب‌های شب) با شناسه بازیکن پیدا می‌شوند.
        game = games.find_for_player(callback.from_user.id)
    if game is None or game.kind != namespace:
        await ui.answer(callback, gtexts.game_gone(), alert=True)
        return

    if isinstance(game, XOGame):
        await _xo_callback(callback, game, games)
    elif isinstance(game, SpyfallGame):
        await _spy_callback(callback, game, games, bot)
    elif isinstance(game, MafiaGame):
        await _mafia_callback(callback, game, games, bot)
    else:  # pragma: no cover - نوع ناشناخته
        await ui.answer(callback)


def build_router() -> Router:
    """روتر تازه می‌سازد (روتر ماژولی فقط یک بار قابل اتصال به Dispatcher است)."""
    router = Router(name="games")
    router.message.register(on_game_command, TextCommand("xo", "spy", "mafia", "stopgame"))
    router.callback_query.register(
        on_game_callback,
        F.data.startswith("xo:") | F.data.startswith("spy:") | F.data.startswith("mafia:"),
    )
    return router
