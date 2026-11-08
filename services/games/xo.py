"""بازی دوز (XO): دونفره با دعوت، یا تک‌نفره با ربات.

منطق بازی خالص است (بدون تلگرام): صفحه، نوبت، برنده و حرکت ربات. لایه تلگرام
فقط صفحه را با دکمه‌های شیشه‌ای نشان می‌دهد.
"""

from __future__ import annotations

from services.games.base import GameError

LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)
EMPTY = ""
BOT_ID = 0  # جای‌نگهدار؛ شناسه واقعی ربات هنگام ساخت بازی داده می‌شود.


class XOGame:
    """یک دست دوز در یک گروه.

    mode = "bot"  → بازیکن اول (X) با ربات (O) بازی می‌کند.
    mode = "duel" → دو بازیکن واقعی؛ بازی تا زدن «قبول» توسط حریف شروع نمی‌شود.
    """

    kind = "xo"

    def __init__(
        self,
        chat_id: int,
        host_id: int,
        host_name: str,
        *,
        mode: str = "bot",
        opponent_id: int | None = None,
        opponent_name: str = "حریف",
    ) -> None:
        self.chat_id = chat_id
        self.host_id = host_id
        self.host_name = host_name
        self.mode = mode
        self.opponent_id = opponent_id if mode == "duel" else BOT_ID
        self.opponent_name = opponent_name
        self.board: list[str] = [EMPTY] * 9
        self.turn = "X"
        self.winner: str | None = None  # "X" | "O" | "draw"
        self.finished = False
        self.awaiting_accept = mode == "duel"

    @property
    def vs_bot(self) -> bool:
        return self.mode == "bot"

    def is_finished(self) -> bool:
        return self.finished

    def has_player(self, user_id: int) -> bool:
        return user_id in (self.host_id, self.opponent_id)

    def name_of(self, mark: str) -> str:
        if mark == "X":
            return self.host_name
        return "ربات" if self.vs_bot else self.opponent_name

    def mark_of(self, user_id: int) -> str | None:
        if user_id == self.host_id:
            return "X"
        if not self.vs_bot and user_id == self.opponent_id:
            return "O"
        return None

    # ----- جریان بازی ---------------------------------------------------------

    def start(self) -> None:
        self.awaiting_accept = False

    def reset(self) -> None:
        """دست تازه با همان بازیکنان."""
        self.board = [EMPTY] * 9
        self.turn = "X"
        self.winner = None
        self.finished = False
        self.awaiting_accept = False

    def play(self, user_id: int, index: int) -> None:
        """حرکت یک بازیکن؛ در صورت نامعتبر بودن `GameError` می‌دهد."""
        if self.finished:
            raise GameError("finished")
        if self.awaiting_accept:
            raise GameError("not_started")
        mark = self.mark_of(user_id)
        if mark is None:
            raise GameError("not_player")
        if mark != self.turn:
            raise GameError("not_your_turn")
        if not 0 <= index < 9:
            raise GameError("bad_cell")
        if self.board[index] != EMPTY:
            raise GameError("taken")
        self._place(index, mark)

    def bot_turn(self) -> int:
        """حرکت ربات (O)؛ شماره خانه یا -1 اگر نوبت او نباشد."""
        if self.finished or self.vs_bot is False or self.turn != "O":
            return -1
        index = self._best_move("O")
        if index < 0:
            return -1
        self._place(index, "O")
        return index

    def _place(self, index: int, mark: str) -> None:
        self.board[index] = mark
        result = self._winner()
        if result is not None:
            self.winner = result
            self.finished = True
            return
        self.turn = "O" if mark == "X" else "X"

    def _winner(self) -> str | None:
        for a, b, c in LINES:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return "draw" if all(self.board) else None

    def _best_move(self, mark: str) -> int:
        """برد فوری → بستن برد حریف → مرکز → گوشه → لبه."""
        opponent = "O" if mark == "X" else "X"
        for target in (mark, opponent):
            for index in range(9):
                if self.board[index] != EMPTY:
                    continue
                self.board[index] = target
                won = self._winner() == target
                self.board[index] = EMPTY
                if won:
                    return index
        if self.board[4] == EMPTY:
            return 4
        for index in (0, 2, 6, 8):
            if self.board[index] == EMPTY:
                return index
        for index in (1, 3, 5, 7):
            if self.board[index] == EMPTY:
                return index
        return -1
