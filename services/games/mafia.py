"""بازی مافیا: تیم مافیا در برابر شهر.

شب: مافیا یک نفر را انتخاب می‌کند، دکتر یک نفر را نجات می‌دهد و کارآگاه هویت
یک نفر را می‌پرسد. روز: گروه بحث می‌کند و با رأی یک نفر اخراج می‌شود.
برد مافیا: تعدادشان با بقیه برابر یا بیشتر شود. برد شهر: همه مافیاها حذف شوند.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from services.games.base import GameError, GamePlayer

ROLE_MAFIA = "mafia"
ROLE_DOCTOR = "doctor"
ROLE_DETECTIVE = "detective"
ROLE_CITIZEN = "citizen"

PHASE_LOBBY = "lobby"
PHASE_NIGHT = "night"
PHASE_DAY = "day"
PHASE_VOTE = "vote"
PHASE_FINISHED = "finished"

WIN_MAFIA = "mafia"
WIN_CITY = "city"


@dataclass(frozen=True, slots=True)
class NightResult:
    """نتیجه یک شب: قربانی (اگر بود) و اینکه دکتر نجات داده یا نه."""

    killed: GamePlayer | None
    saved: bool


class MafiaGame:
    kind = "mafia"
    MIN_PLAYERS = 4
    MAX_PLAYERS = 12

    def __init__(self, chat_id: int, host_id: int, host_name: str) -> None:
        self.chat_id = chat_id
        self.host_id = host_id
        self.host_name = host_name
        self.players: list[GamePlayer] = []
        self.phase = PHASE_LOBBY
        self.night_number = 0
        # انتخاب‌های شب: actor user_id → target user_id (None = رد کردن)
        self.night_actions: dict[int, int | None] = {}
        self.votes: dict[int, int] = {}
        self.winner: str | None = None

    # ----- بازیکنان -----------------------------------------------------------

    def has_player(self, user_id: int) -> bool:
        return any(player.user_id == user_id for player in self.players)

    def is_finished(self) -> bool:
        return self.phase == PHASE_FINISHED

    def player(self, user_id: int) -> GamePlayer | None:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    @property
    def names(self) -> list[str]:
        return [player.name for player in self.players]

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

    def alive_players(self) -> list[GamePlayer]:
        return [player for player in self.players if player.alive]

    def mafia_players(self) -> list[GamePlayer]:
        return [player for player in self.players if player.role == ROLE_MAFIA]

    def teammates_of(self, user_id: int) -> list[str]:
        return [
            player.name
            for player in self.mafia_players()
            if player.user_id != user_id
        ]

    def targets_alive(self, *, exclude_mafia: bool = False, exclude_id: int | None = None) -> list[GamePlayer]:
        targets = []
        for player in self.alive_players():
            if exclude_mafia and player.role == ROLE_MAFIA:
                continue
            if exclude_id is not None and player.user_id == exclude_id:
                continue
            targets.append(player)
        return targets

    # ----- شروع ---------------------------------------------------------------

    def start(self, rng: random.Random | None = None) -> None:
        """نقش‌ها را پخش می‌کند: مافیا، دکتر، کارآگاه (در گروه‌های بزرگ‌تر) و شهروند."""
        if self.phase != PHASE_LOBBY:
            raise GameError("started")
        count = len(self.players)
        if count < self.MIN_PLAYERS:
            raise GameError("need_players")

        mafia_count = 2 if count >= 7 else 1
        roles = [ROLE_MAFIA] * mafia_count
        roles.append(ROLE_DOCTOR)
        if count >= 5:
            roles.append(ROLE_DETECTIVE)
        roles += [ROLE_CITIZEN] * (count - len(roles))

        picker = rng or random
        picker.shuffle(roles)
        for player, role in zip(self.players, roles, strict=True):
            player.role = role
            player.alive = True
        self.phase = PHASE_DAY
        self.night_number = 0

    # ----- شب -----------------------------------------------------------------

    def begin_night(self) -> None:
        if self.phase == PHASE_FINISHED:
            raise GameError("finished")
        self.night_number += 1
        self.phase = PHASE_NIGHT
        self.night_actions = {}

    def _actor_for(self, user_id: int, role: str) -> GamePlayer:
        player = self.player(user_id)
        if player is None:
            raise GameError("not_player")
        if not player.alive:
            raise GameError("dead")
        if player.role != role:
            raise GameError("not_your_role")
        if self.phase != PHASE_NIGHT:
            raise GameError("not_night")
        return player

    def _check_target(self, target_id: int | None) -> int | None:
        if target_id is None:
            return None
        target = self.player(target_id)
        if target is None or not target.alive:
            raise GameError("bad_target")
        return target_id

    def submit_kill(self, actor_id: int, target_id: int | None) -> None:
        self._actor_for(actor_id, ROLE_MAFIA)
        target = self._check_target(target_id)
        if target is not None and self.player(target).role == ROLE_MAFIA:
            raise GameError("bad_target")
        self.night_actions[actor_id] = target

    def submit_save(self, actor_id: int, target_id: int | None) -> None:
        self._actor_for(actor_id, ROLE_DOCTOR)
        self.night_actions[actor_id] = self._check_target(target_id)

    def submit_check(self, actor_id: int, target_id: int | None) -> bool:
        """استعلام کارآگاه؛ True یعنی هدف مافیا است."""
        self._actor_for(actor_id, ROLE_DETECTIVE)
        if target_id is None:
            raise GameError("bad_target")
        if target_id == actor_id:
            raise GameError("bad_target")
        target = self._check_target(target_id)
        self.night_actions[actor_id] = target
        return self.player(target).role == ROLE_MAFIA

    def _acted(self, role: str) -> bool:
        return any(
            self.player(actor_id).role == role
            for actor_id in self.night_actions
            if self.player(actor_id) is not None
        )

    def night_ready(self) -> bool:
        """همه نقش‌های زنده انتخابشان را کرده‌اند؟"""
        if self.phase != PHASE_NIGHT:
            return False
        roles = {player.role for player in self.alive_players()}
        return all(self._acted(role) for role in roles if role != ROLE_CITIZEN)

    def resolve_night(self) -> NightResult:
        """شب را جمع‌بندی می‌کند: قربانی مشخص و حذف می‌شود (اگر دکتر نجاتش نداده باشد)."""
        if self.phase != PHASE_NIGHT:
            raise GameError("not_night")

        kill_target: int | None = None
        for actor_id, target in self.night_actions.items():
            player = self.player(actor_id)
            if player is not None and player.role == ROLE_MAFIA and target is not None:
                kill_target = target

        save_target: int | None = None
        for actor_id, target in self.night_actions.items():
            player = self.player(actor_id)
            if player is not None and player.role == ROLE_DOCTOR and target is not None:
                save_target = target

        saved = kill_target is not None and kill_target == save_target
        killed: GamePlayer | None = None
        if kill_target is not None and not saved:
            killed = self.player(kill_target)
            if killed is not None:
                killed.alive = False

        self.phase = PHASE_DAY
        self.night_actions = {}
        return NightResult(killed=killed, saved=saved)

    # ----- رأی‌گیری روز -------------------------------------------------------

    def begin_vote(self) -> None:
        if self.phase in (PHASE_FINISHED, PHASE_LOBBY):
            raise GameError("finished")
        self.phase = PHASE_VOTE
        self.votes = {}

    def cast_vote(self, voter_id: int, target_id: int) -> None:
        if self.phase != PHASE_VOTE:
            raise GameError("not_voting")
        voter = self.player(voter_id)
        if voter is None or not voter.alive:
            raise GameError("not_player")
        target = self.player(target_id)
        if target is None or not target.alive:
            raise GameError("bad_target")
        if voter_id == target_id:
            raise GameError("self_vote")
        self.votes[voter_id] = target_id

    def resolve_vote(self) -> GamePlayer | None:
        """بیشترین رأی اخراج می‌شود؛ در تساوی کسی اخراج نمی‌شود."""
        if self.phase != PHASE_VOTE:
            raise GameError("not_voting")
        eliminated: GamePlayer | None = None
        if self.votes:
            counts: dict[int, int] = {}
            for target in self.votes.values():
                counts[target] = counts.get(target, 0) + 1
            top = max(counts.values())
            leaders = [user_id for user_id, count in counts.items() if count == top]
            if len(leaders) == 1:
                eliminated = self.player(leaders[0])
                if eliminated is not None:
                    eliminated.alive = False
        self.votes = {}
        self.phase = PHASE_DAY
        return eliminated

    # ----- پایان --------------------------------------------------------------

    def winner_side(self) -> str | None:
        mafia_alive = len([player for player in self.alive_players() if player.role == ROLE_MAFIA])
        others_alive = len(self.alive_players()) - mafia_alive
        if mafia_alive == 0:
            return WIN_CITY
        if mafia_alive >= others_alive:
            return WIN_MAFIA
        return None

    def finish(self, winner: str) -> None:
        self.phase = PHASE_FINISHED
        self.winner = winner

    def reveal(self) -> list[tuple[str, str]]:
        """(نام، نقش) همه بازیکنان برای اعلام پایان بازی."""
        return [(player.name, player.role or ROLE_CITIZEN) for player in self.players]
