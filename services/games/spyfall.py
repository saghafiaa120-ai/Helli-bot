"""بازی اسپای (Spyfall).

همه یک مکان مشترک می‌گیرند، جز یک نفر که جاسوس است. بازیکنان در گروه از هم
سؤال می‌پرسند؛ اگر جاسوس لو برود شهروندان برنده‌اند، وگرنه جاسوس با حدس درست
مکان برنده می‌شود.
"""

from __future__ import annotations

import random

from services.games.base import GameError, GamePlayer

LOCATIONS: tuple[str, ...] = (
    "بیمارستان",
    "فرودگاه",
    "هتل",
    "رستوران",
    "مدرسه",
    "بانک",
    "سینما",
    "پارک",
    "ورزشگاه",
    "کشتی تفریحی",
    "قطار",
    "سفارت",
    "دانشگاه",
    "سوپرمارکت",
    "کتابخانه",
    "زندان",
    "کلانتری",
    "ایستگاه آتش‌نشانی",
    "موزه",
    "کافه",
    "شرکت",
    "بندر",
    "ایستگاه فضایی",
    "هواپیما",
)

PHASE_LOBBY = "lobby"
PHASE_PLAYING = "playing"
PHASE_VOTING = "voting"
PHASE_FINISHED = "finished"

WIN_SPIES = "spies"
WIN_CITIZENS = "citizens"


class SpyfallGame:
    kind = "spy"
    MIN_PLAYERS = 3
    MAX_PLAYERS = 10

    def __init__(self, chat_id: int, host_id: int, host_name: str) -> None:
        self.chat_id = chat_id
        self.host_id = host_id
        self.host_name = host_name
        self.players: list[GamePlayer] = []
        self.phase = PHASE_LOBBY
        self.location: str | None = None
        self.location_index: int | None = None
        self.spy_id: int | None = None
        self.votes: dict[int, int] = {}
        self.guessed = False
        self.winner: str | None = None

    # ----- بازیکنان -----------------------------------------------------------

    @property
    def names(self) -> list[str]:
        return [player.name for player in self.players]

    def is_finished(self) -> bool:
        return self.phase == PHASE_FINISHED

    def has_player(self, user_id: int) -> bool:
        return any(player.user_id == user_id for player in self.players)

    def player(self, user_id: int) -> GamePlayer | None:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def add_player(self, user_id: int, name: str) -> None:
        if self.phase != PHASE_LOBBY:
            raise GameError("started")
        if self.has_player(user_id):
            raise GameError("already_joined")
        if len(self.players) >= self.MAX_PLAYERS:
            raise GameError("full")
        self.players.append(GamePlayer(user_id=user_id, name=name))

    def remove_player(self, user_id: int) -> bool:
        if self.phase != PHASE_LOBBY:
            raise GameError("started")
        before = len(self.players)
        self.players = [player for player in self.players if player.user_id != user_id]
        return len(self.players) != before

    # ----- جریان بازی ---------------------------------------------------------

    def start(self, rng: random.Random | None = None) -> None:
        if self.phase != PHASE_LOBBY:
            raise GameError("started")
        if len(self.players) < self.MIN_PLAYERS:
            raise GameError("need_players")
        picker = rng or random
        self.location_index = picker.randrange(len(LOCATIONS))
        self.location = LOCATIONS[self.location_index]
        spy = picker.choice(self.players)
        self.spy_id = spy.user_id
        for player in self.players:
            player.role = "spy" if player.user_id == self.spy_id else "citizen"
        self.phase = PHASE_PLAYING

    def reset_to_lobby(self) -> None:
        """اگر ارسال نقش‌ها شکست خورد، بازی به حالت انتظار برمی‌گردد."""
        self.phase = PHASE_LOBBY
        self.location = None
        self.location_index = None
        self.spy_id = None
        self.votes = {}
        self.guessed = False
        self.winner = None
        for player in self.players:
            player.role = None

    def begin_vote(self) -> None:
        if self.phase not in (PHASE_PLAYING, PHASE_VOTING):
            raise GameError("finished")
        self.phase = PHASE_VOTING
        self.votes = {}

    def cast_vote(self, voter_id: int, target_id: int) -> None:
        if self.phase != PHASE_VOTING:
            raise GameError("not_voting")
        if not self.has_player(voter_id):
            raise GameError("not_player")
        if not self.has_player(target_id):
            raise GameError("bad_target")
        if voter_id == target_id:
            raise GameError("self_vote")
        self.votes[voter_id] = target_id

    def resolve_vote(self) -> tuple[str, int | None]:
        """نتیجه رأی‌گیری: ("spy"|"wrong"|"tie", متهم).

        رأی اکثریت نسبی کافی است؛ در تساوی رأی، کسی حذف نمی‌شود و بازی ادامه دارد.
        """
        if self.phase != PHASE_VOTING:
            raise GameError("not_voting")
        if not self.votes:
            return ("tie", None)

        counts: dict[int, int] = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1
        top = max(counts.values())
        leaders = [user_id for user_id, count in counts.items() if count == top]
        if len(leaders) > 1:
            self.votes = {}
            self.phase = PHASE_PLAYING
            return ("tie", None)

        accused = leaders[0]
        if accused == self.spy_id:
            self.finish(WIN_CITIZENS)
            return ("spy", accused)
        self.finish(WIN_SPIES)
        return ("wrong", accused)

    def guess(self, user_id: int, index: int) -> bool:
        """حدس مکان توسط جاسوس؛ True یعنی درست حدس زد."""
        if self.phase not in (PHASE_PLAYING, PHASE_VOTING):
            raise GameError("finished")
        if user_id != self.spy_id:
            raise GameError("not_spy")
        if self.guessed:
            raise GameError("already_guessed")
        if not 0 <= index < len(LOCATIONS):
            raise GameError("bad_target")
        self.guessed = True
        correct = index == self.location_index
        self.finish(WIN_SPIES if correct else WIN_CITIZENS)
        return correct

    def finish(self, winner: str) -> None:
        self.phase = PHASE_FINISHED
        self.winner = winner
