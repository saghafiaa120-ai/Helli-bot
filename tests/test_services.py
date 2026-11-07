"""تست سرویس‌ها روی SQLite درون‌حافظه.

نیازمند sqlalchemy، aiosqlite و pytest-asyncio است؛ در غیر این صورت رد می‌شود.
"""

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")
pytest_asyncio = pytest.importorskip("pytest_asyncio")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import database.models  # noqa: E402,F401
from core.enums import AuditAction, HelliRole  # noqa: E402
from database.base import Base  # noqa: E402
from database.models import AuditLog, Group, GroupAdmin, GroupMember, GroupSettings, User  # noqa: E402
from domain.dto import AdminInfo, BotStatus, ChatRef, UserRef  # noqa: E402
from services.admin_service import AdminService  # noqa: E402
from services.group_service import GroupService  # noqa: E402
from services.membership_service import MembershipService  # noqa: E402
from services.user_service import UserService  # noqa: E402

CHAT = ChatRef(platform="telegram", external_id=-100111, title="گروه آزمایشی", kind="supergroup")


def _user(external_id, **kw):
    return UserRef(platform="telegram", external_id=external_id, first_name=kw.pop("first_name", "کاربر"), **kw)


def _admin(external_id, role="admin", **kw):
    return AdminInfo(user=_user(external_id, **kw), platform_role=role, permissions={"can_delete_messages": True})


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _count(session, model):
    return len((await session.execute(select(model))).scalars().all())


async def test_register_creates_group_settings_and_audit(session):
    group, joined = await GroupService(session).register(CHAT, BotStatus(is_admin=True))
    assert joined and group.is_active and group.bot_is_admin
    assert await _count(session, Group) == 1
    assert await _count(session, GroupSettings) == 1
    log = (await session.execute(select(AuditLog))).scalar_one()
    assert log.action == AuditAction.GROUP_REGISTERED.value


async def test_register_is_idempotent(session):
    service = GroupService(session)
    await service.register(CHAT)
    group, joined = await service.register(CHAT, BotStatus(is_admin=True))
    assert not joined and group.bot_is_admin
    assert await _count(session, Group) == 1
    assert await _count(session, AuditLog) == 1


async def test_bot_removed_then_readded(session):
    service = GroupService(session)
    await service.register(CHAT, BotStatus(is_admin=True))
    group = await service.mark_bot_removed(CHAT)
    assert group is not None and not group.is_active and group.left_at is not None
    assert await service.mark_bot_removed(CHAT) is None  # بار دوم کاری نمی‌کند

    group, joined = await service.register(CHAT)
    assert joined and group.is_active and group.left_at is None


async def test_ensure_creates_group_seen_by_activity(session):
    group, created = await GroupService(session).ensure(CHAT)
    assert created and group.title == "گروه آزمایشی"


async def test_title_is_updated(session):
    service = GroupService(session)
    await service.register(CHAT)
    renamed = ChatRef(platform="telegram", external_id=CHAT.external_id, title="نام جدید", kind="supergroup")
    group, _ = await service.register(renamed)
    assert group.title == "نام جدید"


async def test_migrate_changes_external_id_and_keeps_history(session):
    service = GroupService(session)
    group, _ = await service.register(CHAT)
    migrated = await service.migrate("telegram", CHAT.external_id, -100999)
    assert migrated.id == group.id and migrated.external_id == -100999
    assert await service.migrate("telegram", 12345, 1) is None


async def test_migrate_to_already_registered_id_deactivates_old(session):
    service = GroupService(session)
    old, _ = await service.register(CHAT)
    new_chat = ChatRef(platform="telegram", external_id=-100999, title="جدید", kind="supergroup")
    await service.register(new_chat)
    result = await service.migrate("telegram", CHAT.external_id, -100999)
    assert result.id == old.id and not result.is_active
    assert result.external_id == CHAT.external_id


async def test_user_upsert_updates_changed_fields(session):
    service = UserService(session)
    first = await service.upsert(_user(7, username="old"))
    second = await service.upsert(_user(7, username="new", first_name="نام"))
    assert first.id == second.id
    assert second.username == "new" and second.first_name == "نام"
    assert await _count(session, User) == 1


async def test_sync_admins_adds_updates_and_removes(session):
    group, _ = await GroupService(session).register(CHAT)
    service = AdminService(session)

    added, removed = await service.sync_admins(group.id, [_admin(1, "creator"), _admin(2)])
    assert len(added) == 2 and not removed
    assert await _count(session, GroupAdmin) == 2

    owner = await UserService(session).upsert(_user(1))
    admin = await UserService(session).upsert(_user(2))
    assert await service.get_role(group.id, owner.id) is HelliRole.OWNER
    assert await service.get_role(group.id, admin.id) is HelliRole.ADMIN

    added, removed = await service.sync_admins(group.id, [_admin(1, "creator")])
    assert not added and removed == {admin.id}
    assert await service.get_role(group.id, admin.id) is None


async def test_sync_admins_ignores_bots_and_keeps_manual_moderators(session):
    group, _ = await GroupService(session).register(CHAT)
    service = AdminService(session)
    await service.sync_admins(group.id, [_admin(5, is_bot=True)])
    assert await _count(session, GroupAdmin) == 0

    mod = await UserService(session).upsert(_user(9))
    session.add(GroupAdmin(group_id=group.id, user_id=mod.id, helli_role=HelliRole.MODERATOR.value))
    await session.flush()

    await service.sync_admins(group.id, [_admin(1, "creator")])
    assert await service.get_role(group.id, mod.id) is HelliRole.MODERATOR


async def test_membership_transitions(session):
    group, _ = await GroupService(session).register(CHAT)
    user = await UserService(session).upsert(_user(3))
    members = MembershipService(session)

    row = await members.set_status(group.id, user.id, "member")
    assert row.status == "member" and row.joined_at is not None

    row = await members.set_status(group.id, user.id, "left")
    assert row.status == "left" and row.left_at is not None

    row = await members.touch_activity(group.id, user.id)
    assert row.status == "member" and row.left_at is None and row.last_active_at is not None
    assert await _count(session, GroupMember) == 1
