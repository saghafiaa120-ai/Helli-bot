"""تست منطق بازی‌ها (بدون تلگرام): دوز، اسپای و مافیا."""

from __future__ import annotations

import random

import pytest

from services.games.base import GameError, GameRegistry
from services.games.mafia import (
    PHASE_DAY,
    PHASE_FINISHED,
    ROLE_CITIZEN,
    ROLE_DETECTIVE,
    ROLE_DOCTOR,
    ROLE_MAFIA,
    WIN_CITY,
    WIN_MAFIA,
    MafiaGame,
)
from services.games.spyfall import (
    LOCATIONS,
    PHASE_PLAYING,
    SpyfallGame,
)
from services.games.spyfall import (
    PHASE_FINISHED as SPY_FINISHED,
)
from services.games.xo import XOGame

# ----- دوز --------------------------------------------------------------------------


def test_xo_first_player_wins_with_a_line():
    game = XOGame(1, 10, "علی", mode="duel", opponent_id=20, opponent_name="رضا")
    game.start()

    for index in (0, 4, 8):  # علی
        game.play(10, index)
        if game.finished:
            break
        game.play(20, (1, 2)[(0, 4, 8).index(index)])

    assert game.finished
    assert game.winner == "X"


def test_xo_rejects_out_of_turn_and_taken_cells():
    game = XOGame(1, 10, "علی", mode="duel", opponent_id=20, opponent_name="رضا")
    game.start()
    game.play(10, 0)

    with pytest.raises(GameError) as exc:
        game.play(10, 1)
    assert exc.value.kind == "not_your_turn"

    with pytest.raises(GameError) as exc:
        game.play(20, 0)
    assert exc.value.kind == "taken"


def test_xo_draw_when_board_is_full():
    game = XOGame(1, 10, "علی", mode="duel", opponent_id=20, opponent_name="رضا")
    game.start()
    # ترتیب کشیدن مساوی
    moves = [(10, 0), (20, 1), (10, 2), (20, 3), (10, 5), (20, 4), (10, 6), (20, 8), (10, 7)]
    for user_id, index in moves:
        game.play(user_id, index)

    assert game.finished
    assert game.winner == "draw"


def test_xo_bot_blocks_a_winning_line():
    game = XOGame(1, 10, "علی", mode="bot", opponent_id=999)
    game.start()
    game.play(10, 0)  # X
    game.bot_turn()  # O
    game.play(10, 1)  # X تهدید به برد با خانه ۲
    game.bot_turn()

    assert game.board[2] == "O"


def test_xo_duel_needs_accept_before_moves():
    game = XOGame(1, 10, "علی", mode="duel", opponent_id=20, opponent_name="رضا")
    with pytest.raises(GameError) as exc:
        game.play(10, 0)
    assert exc.value.kind == "not_started"


# ----- اسپای ------------------------------------------------------------------------


def _spy_game(count: int = 4) -> SpyfallGame:
    game = SpyfallGame(1, 100, "میزبان")
    for index in range(count):
        game.add_player(100 + index, f"بازیکن{index}")
    return game


def test_spyfall_assigns_exactly_one_spy_and_a_location():
    game = _spy_game()
    game.start(random.Random(7))

    spies = [player for player in game.players if player.role == "spy"]
    assert len(spies) == 1
    assert game.spy_id == spies[0].user_id
    assert game.location in LOCATIONS
    assert game.phase == PHASE_PLAYING


def test_spyfall_needs_minimum_players():
    game = SpyfallGame(1, 100, "میزبان")
    game.add_player(100, "میزبان")
    game.add_player(101, "دومی")
    with pytest.raises(GameError) as exc:
        game.start()
    assert exc.value.kind == "need_players"


def test_spyfall_catching_the_spy_gives_citizens_the_win():
    game = _spy_game(3)
    game.start(random.Random(1))
    game.begin_vote()
    spy_id = game.spy_id
    for player in game.players:
        if player.user_id != spy_id:
            game.cast_vote(player.user_id, spy_id)

    outcome, accused = game.resolve_vote()
    assert outcome == "spy"
    assert accused == spy_id
    assert game.winner == "citizens"
    assert game.phase == SPY_FINISHED


def test_spyfall_wrong_accusation_gives_spy_the_win():
    game = _spy_game(3)
    game.start(random.Random(2))
    game.begin_vote()
    spy_id = game.spy_id
    innocent = next(p for p in game.players if p.user_id != spy_id)
    for player in game.players:
        if player.user_id != innocent.user_id:
            game.cast_vote(player.user_id, innocent.user_id)

    outcome, accused = game.resolve_vote()
    assert outcome == "wrong"
    assert accused == innocent.user_id
    assert game.winner == "spies"


def test_spyfall_correct_guess_wins_for_spy():
    game = _spy_game(3)
    game.start(random.Random(3))
    assert game.guess(game.spy_id, game.location_index) is True
    assert game.winner == "spies"

    with pytest.raises(GameError) as exc:
        game.guess(game.spy_id, 0)
    assert exc.value.kind == "finished"


def test_spyfall_only_spy_can_guess():
    game = _spy_game(3)
    game.start(random.Random(4))
    other = next(p for p in game.players if p.user_id != game.spy_id)
    with pytest.raises(GameError) as exc:
        game.guess(other.user_id, 0)
    assert exc.value.kind == "not_spy"


# ----- مافیا ------------------------------------------------------------------------


def _mafia_game(count: int = 5, seed: int = 11) -> MafiaGame:
    game = MafiaGame(1, 100, "میزبان")
    for index in range(count):
        game.add_player(100 + index, f"بازیکن{index}")
    game.start(random.Random(seed))
    return game


def _by_role(game: MafiaGame, role: str) -> list:
    return [player for player in game.players if player.role == role]


def test_mafia_role_distribution():
    game = _mafia_game(5)
    roles = [player.role for player in game.players]
    assert roles.count(ROLE_MAFIA) == 1
    assert roles.count(ROLE_DOCTOR) == 1
    assert roles.count(ROLE_DETECTIVE) == 1
    assert roles.count(ROLE_CITIZEN) == 2

    big = _mafia_game(8, seed=5)
    assert [player.role for player in big.players].count(ROLE_MAFIA) == 2


def test_mafia_night_kills_target_when_doctor_saves_someone_else():
    game = _mafia_game()
    game.begin_night()
    mafia = _by_role(game, ROLE_MAFIA)[0]
    doctor = _by_role(game, ROLE_DOCTOR)[0]
    target = next(p for p in game.players if p.role == ROLE_CITIZEN)

    game.submit_kill(mafia.user_id, target.user_id)
    game.submit_save(doctor.user_id, mafia.user_id)
    detective = _by_role(game, ROLE_DETECTIVE)[0]
    game.submit_check(detective.user_id, mafia.user_id)
    assert game.night_ready()

    result = game.resolve_night()
    assert result.killed is target
    assert not target.alive
    assert not result.saved
    assert game.phase == PHASE_DAY


def test_mafia_doctor_can_save_the_target():
    game = _mafia_game()
    game.begin_night()
    mafia = _by_role(game, ROLE_MAFIA)[0]
    doctor = _by_role(game, ROLE_DOCTOR)[0]
    target = next(p for p in game.players if p.role == ROLE_CITIZEN)

    game.submit_kill(mafia.user_id, target.user_id)
    game.submit_save(doctor.user_id, target.user_id)
    result = game.resolve_night()

    assert result.saved
    assert result.killed is None
    assert target.alive


def test_mafia_detective_check_returns_role():
    game = _mafia_game()
    game.begin_night()
    detective = _by_role(game, ROLE_DETECTIVE)[0]
    mafia = _by_role(game, ROLE_MAFIA)[0]
    citizen = next(p for p in game.players if p.role == ROLE_CITIZEN)

    assert game.submit_check(detective.user_id, mafia.user_id) is True
    assert game.submit_check(detective.user_id, citizen.user_id) is False


def test_mafia_mafia_cannot_kill_a_teammate():
    game = _mafia_game(8, seed=5)
    game.begin_night()
    mafia = _by_role(game, ROLE_MAFIA)
    with pytest.raises(GameError) as exc:
        game.submit_kill(mafia[0].user_id, mafia[1].user_id)
    assert exc.value.kind == "bad_target"


def test_mafia_citizens_win_when_last_mafia_is_eliminated():
    game = _mafia_game()
    game.begin_vote()
    mafia = _by_role(game, ROLE_MAFIA)[0]
    for player in game.players:
        if player.user_id != mafia.user_id:
            game.cast_vote(player.user_id, mafia.user_id)

    eliminated = game.resolve_vote()
    assert eliminated is mafia
    assert not mafia.alive
    assert game.winner_side() == WIN_CITY
    game.finish(WIN_CITY)
    assert game.phase == PHASE_FINISHED


def test_mafia_wins_when_mafia_reaches_parity():
    game = _mafia_game(4, seed=3)
    # سه نفر غیرمافیا را حذف می‌کنیم تا مافیا برابر بقیه شود
    for player in game.players:
        if player.role != ROLE_MAFIA:
            player.alive = False
    assert game.winner_side() == WIN_MAFIA


def test_mafia_tie_vote_eliminates_nobody():
    game = _mafia_game()
    game.begin_vote()
    first, second = game.alive_players()[:2]
    game.cast_vote(first.user_id, second.user_id)
    game.cast_vote(second.user_id, first.user_id)
    assert game.resolve_vote() is None
    assert game.phase == PHASE_DAY


def test_mafia_night_requires_all_special_roles():
    game = _mafia_game()
    game.begin_night()
    mafia = _by_role(game, ROLE_MAFIA)[0]
    target = next(p for p in game.players if p.role == ROLE_CITIZEN)
    game.submit_kill(mafia.user_id, target.user_id)
    assert game.night_ready() is False


# ----- ثبت بازی‌ها -------------------------------------------------------------------


def test_registry_keeps_one_game_per_chat_and_finds_players():
    registry = GameRegistry()
    xo = XOGame(1, 10, "علی", mode="duel", opponent_id=20, opponent_name="رضا")
    registry.set(1, xo)

    assert registry.get(1) is xo
    assert registry.find_for_player(20) is xo
    assert registry.find_for_player(99) is None

    registry.drop(1, xo)
    assert registry.get(1) is None
