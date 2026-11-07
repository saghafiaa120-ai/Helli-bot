"""تست شمارش پیام‌ها و آمار روزانه."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")
pytest_asyncio = pytest.importorskip("pytest_asyncio")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import database.models  # noqa: E402,F401
from database.base import Base  # noqa: E402
from database.repositories.stats import StatsRepository  # noqa: E402
from domain.dto import BotStatus, ChatRef, UserRef  # noqa: E402
from services.group_service import GroupService  # noqa: E402
from services.message_counter import MessageCounter  # noqa: E402
from services.stats_service import StatsService, flush_counter  # noqa: E402
from services.user_service import UserService  # noqa: E402

CHAT = ChatRef(platform="telegram", external_id=-100777, title="گروه آمار", kind="supergroup")
DAY = date(2026, 11, 7)


@pytest_asyncio.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _group(session):
    group, _ = await GroupService(session).register(CHAT, BotStatus(is_admin=True))
    await UserService(session).upsert(UserRef(platform="telegram", external_id=1, first_name="علی"))
    await UserService(session).upsert(UserRef(platform="telegram", external_id=2, first_name="سارا"))
    return group


async def test_counter_accumulates_and_drains():
    counter = MessageCounter()
    for _ in range(3):
        counter.add("telegram", -100777, 1, DAY)
    counter.add("telegram", -100777, 2, DAY)
    assert counter.total() == 4 and counter.pending() == 2

    rows = counter.drain()
    assert len(rows) == 2
    assert counter.total() == 0 and counter.pending() == 0


async def test_restore_puts_rows_back():
    counter = MessageCounter()
    counter.add("telegram", -100777, 1, DAY)
    rows = counter.drain()
    counter.restore(rows)
    assert counter.total() == 1


async def test_flush_writes_and_merges_repeated_flushes(factory):
    counter = MessageCounter()
    counter.add("telegram", -100777, 1, DAY)
    counter.add("telegram", -100777, 1, DAY)
    assert await flush_counter(factory, counter) == 1

    counter.add("telegram", -100777, 1, DAY)
    await flush_counter(factory, counter)

    async with factory() as session:
        group = await _group(session)
        stats = await StatsService(session).group_day(group, DAY)
        assert stats.total == 3 and stats.people == 1
        await session.commit()


async def test_stats_top_users_and_totals(factory):
    counter = MessageCounter()
    for _ in range(4):
        counter.add("telegram", -100777, 2, DAY)
    for _ in range(2):
        counter.add("telegram", -100777, 1, DAY)
    await flush_counter(factory, counter)

    async with factory() as session:
        group = await _group(session)
        stats = await StatsService(session).group_day(group, DAY)
        assert stats.total == 6 and stats.people == 2
        assert stats.top[0] == ("سارا", 4)
        assert stats.label == "۱۴۰۵/۰۸/۱۶"
        await session.commit()


async def test_stats_are_per_group_and_per_day(factory):
    counter = MessageCounter()
    counter.add("telegram", -100777, 1, DAY)
    counter.add("telegram", -100777, 1, DAY - timedelta(days=1))
    counter.add("telegram", -100888, 1, DAY)
    await flush_counter(factory, counter)

    async with factory() as session:
        group = await _group(session)
        stats = await StatsService(session).group_day(group, DAY)
        assert stats.total == 1
        await session.commit()


async def test_groups_day_returns_map(factory):
    counter = MessageCounter()
    counter.add("telegram", -100777, 1, DAY)
    counter.add("telegram", -100777, 2, DAY)
    await flush_counter(factory, counter)

    async with factory() as session:
        group = await _group(session)
        totals = await StatsService(session).groups_day([group], DAY)
        assert totals[group.id] == (2, 2)
        await session.commit()


async def test_prune_removes_old_days(factory):
    counter = MessageCounter()
    counter.add("telegram", -100777, 1, DAY - timedelta(days=200))
    counter.add("telegram", -100777, 1, DAY)
    await flush_counter(factory, counter)

    async with factory() as session:
        removed = await StatsRepository(session).prune(DAY - timedelta(days=90))
        await session.commit()
        assert removed == 1
        group = await _group(session)
        assert (await StatsService(session).group_day(group, DAY)).total == 1
        await session.commit()


async def test_flush_returns_zero_when_nothing_pending(factory):
    assert await flush_counter(factory, MessageCounter()) == 0
