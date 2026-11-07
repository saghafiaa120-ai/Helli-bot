"""تست جریان پنل کاربری با یک ربات ساختگی (بدون تماس واقعی با تلگرام)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("aiogram")
pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")
pytest_asyncio = pytest.importorskip("pytest_asyncio")

import aiohttp  # noqa: E402
from aiogram import Bot  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage  # noqa: E402
from aiogram.types import Chat, Message, Update  # noqa: E402
from aiogram.types import User as TgUser  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import database.models  # noqa: E402,F401
from core.config import Settings  # noqa: E402
from core.enums import HelliRole  # noqa: E402
from database.base import Base  # noqa: E402
from database.models import GroupAdmin  # noqa: E402
from domain.dto import BotStatus, ChatRef, UserRef  # noqa: E402
from platforms.telegram.adapter import TelegramAdapter  # noqa: E402
from platforms.telegram.app import build_dispatcher  # noqa: E402
from platforms.telegram.confirmations import PendingConfirmations  # noqa: E402
from services.group_service import GroupService  # noqa: E402
from services.message_counter import MessageCounter  # noqa: E402
from services.user_service import UserService  # noqa: E402

TOKEN = "123456789:AAExampleTokenExampleTokenExample123"
GROUP_ID = -100555
ADMIN_ID = 1
GROUP = ChatRef(platform="telegram", external_id=GROUP_ID, title="گروه پنل", kind="supergroup")
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


class FakeSession(BaseSession):
    """همه درخواست‌ها را موفق و بدون تماس شبکه‌ای برمی‌گرداند."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[SendMessage] = []
        self.edited: list[EditMessageText] = []
        self.answered: int = 0
        # برای شبیه‌سازی قطعی گذرای شبکه در ویرایش پیام
        self.fail_edits: int = 0

    async def make_request(self, bot: Bot, method, timeout: int | None = None):
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return self._message(method.chat_id, method.text or "")
        if isinstance(method, EditMessageText):
            if self.fail_edits > 0:
                self.fail_edits -= 1
                raise aiohttp.ServerDisconnectedError("server disconnected")
            self.edited.append(method)
            return True
        if isinstance(method, AnswerCallbackQuery):
            self.answered += 1
            return True
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - استفاده نمی‌شود
        yield b""

    async def close(self) -> None:
        return None

    @staticmethod
    def _message(chat_id: int, text: str) -> Message:
        return Message(
            message_id=len(text) + 1,
            date=NOW,
            chat=Chat(id=chat_id, type="private"),
            text=text,
        )


def _update(text: str, *, chat_id: int, chat_type: str, user_id: int = ADMIN_ID) -> Update:
    chat = Chat(id=chat_id, type=chat_type, title="گروه پنل" if chat_type != "private" else None)
    message = Message(
        message_id=1,
        date=NOW,
        chat=chat,
        from_user=TgUser(id=user_id, is_bot=False, first_name="مدیر"),
        text=text,
    )
    return Update(update_id=1, message=message)


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    session_obj = FakeSession()
    bot = Bot(token=TOKEN, session=session_obj)
    adapter = TelegramAdapter(bot)
    settings = Settings(bot_token=TOKEN, database_url="sqlite+aiosqlite:///:memory:")
    dp = build_dispatcher(factory, adapter, settings, MessageCounter(), PendingConfirmations())
    yield dp, bot, session_obj, factory
    await bot.session.close()
    await engine.dispose()


async def _make_admin(factory) -> int:
    """گروه و مدیر را از قبل ثبت می‌کند و شناسه داخلی گروه را برمی‌گرداند."""
    async with factory() as session:
        group, _ = await GroupService(session).register(GROUP, BotStatus(is_admin=True))
        user = await UserService(session).upsert(
            UserRef(platform="telegram", external_id=ADMIN_ID, first_name="مدیر")
        )
        session.add(
            GroupAdmin(
                group_id=group.id,
                user_id=user.id,
                platform_role="creator",
                permissions={"can_restrict_members": True},
                helli_role=HelliRole.OWNER.value,
            )
        )
        await session.commit()
        return group.id


async def test_panel_in_private_chat_lists_no_groups(env):
    dp, bot, fake, _ = env
    await dp.feed_update(bot, _update("/panel", chat_id=ADMIN_ID, chat_type="private"))

    assert fake.sent, "ربات باید پاسخ بدهد"
    text = fake.sent[-1].text
    assert "پنل کاربری" in text
    assert "هنوز در هیچ گروهی مدیر نیستید" in text


async def test_panel_in_group_requires_admin(env):
    dp, bot, fake, _ = env
    await dp.feed_update(bot, _update("/panel", chat_id=GROUP_ID, chat_type="supergroup", user_id=77))

    assert "فقط مدیران گروه" in fake.sent[-1].text


async def test_panel_in_group_shows_dashboard(env):
    dp, bot, fake, factory = env
    await _make_admin(factory)

    await dp.feed_update(bot, _update("/panel", chat_id=GROUP_ID, chat_type="supergroup"))

    text = fake.sent[-1].text
    assert "پنل مدیریت حلی بات" in text
    assert "گروه پنل" in text
    assert "سازنده گروه" in text
    assert fake.sent[-1].reply_markup is not None


async def test_panel_stats_callback_renders_stats(env):
    dp, bot, fake, factory = env
    group_id = await _make_admin(factory)

    await dp.feed_update(
        bot,
        _update("/panel", chat_id=GROUP_ID, chat_type="supergroup"),
    )
    sent_message = fake.sent[-1]
    callback_update = Update(
        update_id=2,
        callback_query={
            "id": "cb1",
            "chat_instance": "1",
            "from": {"id": ADMIN_ID, "is_bot": False, "first_name": "مدیر"},
            "data": f"panel:stats:{group_id}",
            "message": {
                "message_id": 5,
                "date": int(NOW.timestamp()),
                "chat": {"id": GROUP_ID, "type": "supergroup", "title": "گروه پنل"},
                "text": sent_message.text,
            },
        },
    )
    await dp.feed_update(bot, callback_update)

    assert fake.edited, "پنل باید ویرایش شود"
    assert "آمار" in fake.edited[-1].text


async def test_settings_toggle_changes_value(env):
    dp, bot, fake, factory = env
    group_id = await _make_admin(factory)

    callback_update = Update(
        update_id=3,
        callback_query={
            "id": "cb2",
            "chat_instance": "1",
            "from": {"id": ADMIN_ID, "is_bot": False, "first_name": "مدیر"},
            "data": f"panel:toggle:{group_id}:daily",
            "message": {
                "message_id": 6,
                "date": int(NOW.timestamp()),
                "chat": {"id": GROUP_ID, "type": "supergroup", "title": "گروه پنل"},
                "text": "x",
            },
        },
    )
    await dp.feed_update(bot, callback_update)

    assert fake.edited, "پس از تغییر تنظیم، پنل دوباره رندر می‌شود"
    assert "گزارش شبانه: خاموش" in fake.edited[-1].text


async def test_ban_command_with_duration_bans_user(env):
    dp, bot, fake, factory = env
    await _make_admin(factory)

    await dp.feed_update(
        bot, _update("/ban 222222 1d تبلیغ", chat_id=GROUP_ID, chat_type="supergroup")
    )

    text = fake.sent[-1].text
    assert "مسدود شد" in text
    assert "۱ روز" in text
    assert "تبلیغ" in text


async def test_permanent_ban_asks_for_confirmation(env):
    dp, bot, fake, factory = env
    await _make_admin(factory)

    await dp.feed_update(
        bot, _update("/ban 222222", chat_id=GROUP_ID, chat_type="supergroup")
    )

    text = fake.sent[-1].text
    assert "مسدود کردن دائمی" in text
    assert fake.sent[-1].reply_markup is not None


async def test_persian_alias_command_works(env):
    dp, bot, fake, factory = env
    await _make_admin(factory)

    await dp.feed_update(
        bot, _update("سکوت 222222 ۱۰ دقیقه", chat_id=GROUP_ID, chat_type="supergroup")
    )

    text = fake.sent[-1].text
    assert "بی‌صدا شد" in text
    assert "۱۰ دقیقه" in text


async def test_alias_without_target_shows_usage(env):
    dp, bot, fake, factory = env
    await _make_admin(factory)

    await dp.feed_update(bot, _update("سکوت", chat_id=GROUP_ID, chat_type="supergroup"))

    assert "بی‌صدا کردن" in fake.sent[-1].text


def _callback_update(data: str, message_id: int = 9) -> Update:
    return Update(
        update_id=99,
        callback_query={
            "id": f"cb-{data}",
            "chat_instance": "1",
            "from": {"id": ADMIN_ID, "is_bot": False, "first_name": "مدیر"},
            "data": data,
            "message": {
                "message_id": message_id,
                "date": int(NOW.timestamp()),
                "chat": {"id": GROUP_ID, "type": "supergroup", "title": "گروه پنل"},
                "text": "x",
            },
        },
    )


async def test_panel_retries_after_transient_network_error(env):
    """باگ گزارش‌شده: ServerDisconnectedError روی edit_text نباید پنل را بشکند."""
    dp, bot, fake, factory = env
    group_id = await _make_admin(factory)
    fake.fail_edits = 1

    await dp.feed_update(bot, _callback_update(f"panel:stats:{group_id}"))

    assert fake.edited, "پس از تلاش دوباره، پنل باید ویرایش شود"
    assert fake.answered >= 1, "دکمه باید پاسخ بگیرد تا برای کاربر لودینگ نماند"
    assert "آمار" in fake.edited[-1].text


async def test_panel_resends_message_when_edit_keeps_failing(env):
    dp, bot, fake, factory = env
    group_id = await _make_admin(factory)
    fake.fail_edits = 10  # همه تلاش‌های ویرایش شکست می‌خورند

    await dp.feed_update(bot, _callback_update(f"panel:stats:{group_id}"))

    assert fake.sent, "وقتی ویرایش ممکن نیست، نسخه تازه فرستاده می‌شود"
    assert fake.answered >= 1


async def test_help_sends_sectioned_menu(env):
    dp, bot, fake, _ = env

    await dp.feed_update(bot, _update("/help", chat_id=ADMIN_ID, chat_type="private"))

    sent = fake.sent[-1]
    assert "شروع سریع" in sent.text
    assert sent.reply_markup is not None, "راهنما باید دکمه بخش‌ها را داشته باشد"


async def test_help_section_callback_edits_message(env):
    dp, bot, fake, _ = env

    await dp.feed_update(bot, _callback_update("help:users"))

    assert fake.edited, "بخش راهنما باید همان پیام را ویرایش کند"
    assert "مدیریت کاربران" in fake.edited[-1].text
    assert fake.answered >= 1
