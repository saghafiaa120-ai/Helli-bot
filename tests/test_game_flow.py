"""تست جریان بازی‌ها با یک ربات ساختگی (بدون تماس واقعی با تلگرام)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("aiogram")
pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")
pytest_asyncio = pytest.importorskip("pytest_asyncio")

from aiogram import Bot  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage  # noqa: E402
from aiogram.types import Chat, Message, Update  # noqa: E402
from aiogram.types import User as TgUser  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import database.models  # noqa: E402,F401
from core.config import Settings  # noqa: E402
from database.base import Base  # noqa: E402
from domain.dto import BotStatus, ChatRef  # noqa: E402
from platforms.telegram.adapter import TelegramAdapter  # noqa: E402
from platforms.telegram.app import build_dispatcher  # noqa: E402
from platforms.telegram.confirmations import PendingConfirmations  # noqa: E402
from services.games.base import GameRegistry  # noqa: E402
from services.group_service import GroupService  # noqa: E402
from services.message_counter import MessageCounter  # noqa: E402

TOKEN = "123456789:AAExampleTokenExampleTokenExample123"
GROUP_ID = -100555
HOST_ID = 1
NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


class FakeSession(BaseSession):
    """همه درخواست‌ها را موفق و بدون تماس شبکه‌ای برمی‌گرداند."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[SendMessage] = []
        self.edited: list[EditMessageText] = []
        self.answered: int = 0

    async def make_request(self, bot: Bot, method, timeout: int | None = None):
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return Message(
                message_id=len(self.sent),
                date=NOW,
                chat=Chat(id=int(method.chat_id), type="private"),
                text=method.text or "",
            )
        if isinstance(method, EditMessageText):
            self.edited.append(method)
            return True
        if isinstance(method, AnswerCallbackQuery):
            self.answered += 1
            return True
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def close(self) -> None:
        return None

    def dm_texts(self, user_id: int) -> list[str]:
        return [str(item.text) for item in self.sent if int(item.chat_id) == user_id]


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # گروه را از قبل ثبت می‌کنیم تا میدل‌ور ردیابی سراغ فهرست مدیران تلگرام نرود.
    async with factory() as session:
        await GroupService(session).register(
            ChatRef(platform="telegram", external_id=GROUP_ID, title="گروه بازی", kind="supergroup"),
            BotStatus(is_admin=True),
        )
        await session.commit()

    session_obj = FakeSession()
    bot = Bot(token=TOKEN, session=session_obj)
    adapter = TelegramAdapter(bot)
    settings = Settings(bot_token=TOKEN, database_url="sqlite+aiosqlite:///:memory:")
    dp = build_dispatcher(
        factory,
        adapter,
        settings,
        MessageCounter(),
        PendingConfirmations(),
        GameRegistry(),
    )
    yield dp, bot, session_obj
    await bot.session.close()
    await engine.dispose()


def _update(text: str, *, user_id: int = HOST_ID) -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=NOW,
            chat=Chat(id=GROUP_ID, type="supergroup", title="گروه بازی"),
            from_user=TgUser(id=user_id, is_bot=False, first_name=f"کاربر{user_id}"),
            text=text,
        ),
    )


def _callback(data: str, *, user_id: int) -> Update:
    return Update(
        update_id=2,
        callback_query={
            "id": f"cb-{data}",
            "chat_instance": "1",
            "from": {"id": user_id, "is_bot": False, "first_name": f"کاربر{user_id}"},
            "data": data,
            "message": {
                "message_id": 7,
                "date": int(NOW.timestamp()),
                "chat": {"id": GROUP_ID, "type": "supergroup", "title": "گروه بازی"},
                "text": "بازی",
            },
        },
    )


async def test_xo_starts_against_bot_and_accepts_a_move(env):
    dp, bot, fake = env

    await dp.feed_update(bot, _update("/xo"))

    assert "دوز شروع شد" in fake.sent[-1].text
    assert fake.sent[-1].reply_markup is not None

    await dp.feed_update(bot, _callback("xo:move:4", user_id=HOST_ID))

    assert fake.edited, "پس از حرکت، صفحه به‌روزرسانی می‌شود"
    rows = fake.edited[-1].reply_markup.inline_keyboard
    board = [button.text for row in rows[:3] for button in row]
    assert board[4] == "❌"  # حرکت بازیکن در مرکز
    assert board.count("⭕") == 1  # ربات هم حرکت کرده است


async def test_xo_rejects_move_from_outsider(env):
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/xo"))

    await dp.feed_update(bot, _callback("xo:move:0", user_id=99))

    assert fake.answered == 1
    assert not fake.edited


async def test_spy_lobby_collects_players_and_starts(env):
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/spy"))

    assert "اسپای (جاسوس)" in fake.sent[-1].text

    await dp.feed_update(bot, _callback("spy:join", user_id=2))
    await dp.feed_update(bot, _callback("spy:join", user_id=3))
    await dp.feed_update(bot, _callback("spy:start", user_id=HOST_ID))

    edited = fake.edited[-1].text
    assert "اسپای شروع شد" in edited
    assert "مکان‌های ممکن" in edited
    # نقش‌ها در پیام خصوصی می‌روند: دو شهروند و یک جاسوس
    roles = [text for user_id in (1, 2, 3) for text in fake.dm_texts(user_id)]
    assert sum("نقش شما: شهروند" in text for text in roles) == 2
    assert sum("نقش شما: جاسوس" in text for text in roles) == 1


async def test_spy_start_needs_enough_players(env):
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/spy"))

    await dp.feed_update(bot, _callback("spy:start", user_id=HOST_ID))

    assert fake.answered == 1
    assert "کافی نیست" in str(fake.sent[-1].text) or not fake.edited


async def test_mafia_start_sends_roles_and_opens_night(env):
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/mafia"))

    for user_id in (2, 3, 4, 5):
        await dp.feed_update(bot, _callback("mafia:join", user_id=user_id))
    await dp.feed_update(bot, _callback("mafia:start", user_id=HOST_ID))

    night_messages = [str(item.text) for item in fake.sent if "شب ۱" in str(item.text)]
    assert night_messages, "پیام شروع شب در گروه فرستاده می‌شود"

    role_texts = [text for user_id in (1, 2, 3, 4, 5) for text in fake.dm_texts(user_id)]
    joined = " ".join(role_texts)
    assert "مافیا" in joined and "دکتر" in joined and "کارآگاه" in joined


async def test_second_game_in_same_group_is_rejected(env):
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/xo"))
    await dp.feed_update(bot, _update("/mafia"))

    assert "در جریان است" in str(fake.sent[-1].text)


async def test_stopgame_ends_active_game(env):
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/xo"))
    await dp.feed_update(bot, _update("/stopgame"))

    assert "بازی لغو شد" in str(fake.sent[-1].text)


def _dm_callback(data: str, *, user_id: int) -> Update:
    return Update(
        update_id=3,
        callback_query={
            "id": f"cb-{data}-{user_id}",
            "chat_instance": "1",
            "from": {"id": user_id, "is_bot": False, "first_name": f"کاربر{user_id}"},
            "data": data,
            "message": {
                "message_id": 11,
                "date": int(NOW.timestamp()),
                "chat": {"id": user_id, "type": "private"},
                "text": "انتخاب شب",
            },
        },
    )


async def test_mafia_night_actions_resolve_into_day(env):
    """مافیا، دکتر و کارآگاه انتخاب می‌کنند و شب خودکار جمع‌بندی می‌شود."""
    dp, bot, fake = env
    await dp.feed_update(bot, _update("/mafia"))
    for user_id in (2, 3, 4, 5):
        await dp.feed_update(bot, _callback("mafia:join", user_id=user_id))
    await dp.feed_update(bot, _callback("mafia:start", user_id=HOST_ID))

    roles: dict[str, int] = {}
    for user_id in (1, 2, 3, 4, 5):
        for text in fake.dm_texts(user_id):
            for role, marker in (
                ("mafia", "نقش شما: مافیا"),
                ("doctor", "نقش شما: دکتر"),
                ("detective", "نقش شما: کارآگاه"),
                ("citizen", "نقش شما: شهروند"),
            ):
                if marker in text:
                    roles[role] = user_id
    assert set(roles) == {"mafia", "doctor", "detective", "citizen"}

    # قربانی: یک شهروند غیر از مافیا/دکتر/کارآگاه
    specials = {roles["mafia"], roles["doctor"], roles["detective"]}
    victim = next(user_id for user_id in (1, 2, 3, 4, 5) if user_id not in specials)

    await dp.feed_update(bot, _dm_callback(f"mafia:kill:{victim}", user_id=roles["mafia"]))
    await dp.feed_update(bot, _dm_callback(f"mafia:save:{roles['doctor']}", user_id=roles["doctor"]))
    await dp.feed_update(bot, _dm_callback(f"mafia:check:{roles['mafia']}", user_id=roles["detective"]))

    day_texts = [str(item.text) for item in fake.sent if "☀️" in str(item.text)]
    assert day_texts, "پس از تکمیل انتخاب‌های شب، روز اعلام می‌شود"
    assert "کشته شد" in day_texts[-1]
