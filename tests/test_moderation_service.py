"""تست سرویس مدیریت کاربران روی SQLite درون‌حافظه."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")
pytest_asyncio = pytest.importorskip("pytest_asyncio")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import database.models  # noqa: E402,F401
from core.enums import HelliRole  # noqa: E402
from core.timeutils import utcnow  # noqa: E402
from database.base import Base  # noqa: E402
from database.models import (  # noqa: E402
    GroupAdmin,
    ModerationAction,
    Restriction,
    Warning,
)
from domain.dto import AdminInfo, BotStatus, ChatRef, ModerationSettings, UserRef  # noqa: E402
from platforms.base import Capabilities, PlatformAdapter  # noqa: E402
from services.admin_service import AdminService  # noqa: E402
from services.group_service import GroupService  # noqa: E402
from services.moderation_service import (  # noqa: E402
    Actor,
    ModerationError,
    ModerationService,
)
from services.user_service import UserService  # noqa: E402

CHAT = ChatRef(platform="telegram", external_id=-100555, title="گروه تست", kind="supergroup")
SETTINGS = ModerationSettings(confirm_sensitive_actions=True, warn_limit=3, warn_mute_seconds=3600)


class FakeAdapter(PlatformAdapter):
    platform = "telegram"
    capabilities = Capabilities(
        can_restrict_members=True, can_delete_messages=True, supports_buttons=True
    )
    bot_user_id = 999

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, datetime | None]] = []
        self.banned: set[int] = set()
        self.muted: set[int] = set()

    async def get_admins(self, chat):
        return []

    async def get_bot_status(self, chat):
        return BotStatus(is_admin=True)

    async def get_member_count(self, chat):
        return 10

    async def send_text(self, chat, text):
        return None

    async def ban_member(self, chat, user_id, until):
        self.calls.append(("ban", user_id, until))
        self.banned.add(user_id)

    async def unban_member(self, chat, user_id):
        self.calls.append(("unban", user_id, None))
        if user_id not in self.banned:
            return False
        self.banned.discard(user_id)
        return True

    async def mute_member(self, chat, user_id, until):
        self.calls.append(("mute", user_id, until))
        self.muted.add(user_id)

    async def unmute_member(self, chat, user_id):
        self.calls.append(("unmute", user_id, None))
        if user_id not in self.muted:
            return False
        self.muted.discard(user_id)
        return True

    async def kick_member(self, chat, user_id):
        self.calls.append(("kick", user_id, None))


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _setup(session, *, permissions=None):
    group, _ = await GroupService(session).register(CHAT, BotStatus(is_admin=True))
    users = UserService(session)
    actor_user = await users.upsert(UserRef(platform="telegram", external_id=1, first_name="مدیر"))
    target = await users.upsert(UserRef(platform="telegram", external_id=2, first_name="عضو"))
    actor = Actor(
        user=actor_user,
        role=HelliRole.ADMIN,
        permissions=permissions if permissions is not None else {"can_restrict_members": True},
    )
    return group, actor, target


async def _count(session, model):
    return len((await session.execute(select(model))).scalars().all())


async def test_ban_records_restriction_and_action(session):
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)

    outcome = await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=600, reason="تبلیغ"
    )

    assert outcome.until is not None
    assert adapter.calls == [("ban", 2, outcome.until)]
    restriction = (await session.execute(select(Restriction))).scalar_one()
    assert restriction.kind == "ban" and restriction.is_active
    assert restriction.reason == "تبلیغ"
    action = (await session.execute(select(ModerationAction))).scalar_one()
    assert action.action == "ban" and action.duration_seconds == 600


async def test_permanent_ban_has_no_until(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    outcome = await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=None, reason=None
    )
    assert outcome.until is None


async def test_cannot_moderate_self_bot_or_admin(session):
    group, actor, _target = await _setup(session)
    service = ModerationService(session, FakeAdapter())

    with pytest.raises(ModerationError) as exc:
        await service.ban(
            group=group, chat=CHAT, actor=actor, target=actor.user, duration_seconds=None, reason=None
        )
    assert exc.value.kind == "cannot_target_self"

    admin_row = await UserService(session).upsert(
        UserRef(platform="telegram", external_id=50, first_name="مدیر دیگر")
    )
    session.add(GroupAdmin(group_id=group.id, user_id=admin_row.id, helli_role=HelliRole.ADMIN.value))
    await session.flush()
    with pytest.raises(ModerationError) as exc:
        await service.ban(
            group=group, chat=CHAT, actor=actor, target=admin_row, duration_seconds=None, reason=None
        )
    assert exc.value.kind == "cannot_target_admin"


async def test_actor_without_platform_permission_is_rejected(session):
    group, actor, target = await _setup(session, permissions={"can_restrict_members": False})
    service = ModerationService(session, FakeAdapter())
    with pytest.raises(ModerationError) as exc:
        await service.mute(
            group=group, chat=CHAT, actor=actor, target=target, duration_seconds=None, reason=None
        )
    assert exc.value.kind == "missing_platform_permission"


async def test_plain_member_cannot_moderate(session):
    group, _, target = await _setup(session)
    member = Actor(user=target, role=None)
    service = ModerationService(session, FakeAdapter())
    with pytest.raises(ModerationError) as exc:
        await service.kick(group=group, chat=CHAT, actor=member, target=target, reason=None)
    assert exc.value.kind == "not_authorized"


async def test_unban_reports_when_user_was_not_banned(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    assert await service.unban(group=group, chat=CHAT, actor=actor, target=target) is False


async def test_warn_limit_triggers_temporary_mute_and_resets(session):
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)

    for _ in range(2):
        outcome = await service.warn(
            group=group, chat=CHAT, actor=actor, target=target, reason="اسپم", settings=SETTINGS
        )
        assert outcome.auto_mute_seconds is None

    outcome = await service.warn(
        group=group, chat=CHAT, actor=actor, target=target, reason="اسپم", settings=SETTINGS
    )
    assert outcome.auto_mute_seconds == SETTINGS.warn_mute_seconds
    assert outcome.auto_mute_until is not None

    active_warnings = await session.execute(select(Warning).where(Warning.is_active.is_(True)))
    assert active_warnings.scalars().all() == []
    assert await _count(session, Warning) == 3  # تاریخچه حفظ می‌شود
    mute = (await session.execute(select(Restriction).where(Restriction.kind == "mute"))).scalar_one()
    assert mute.is_active and mute.reason


async def test_warn_limit_zero_never_mutes(session):
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)
    settings = ModerationSettings(warn_limit=0)
    for _ in range(5):
        outcome = await service.warn(
            group=group, chat=CHAT, actor=actor, target=target, reason=None, settings=settings
        )
    assert outcome.auto_mute_seconds is None and outcome.count == 5
    assert "mute" not in [call[0] for call in adapter.calls]


async def test_unwarn_without_warning_raises(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    with pytest.raises(ModerationError) as exc:
        await service.unwarn(group=group, actor=actor, target=target)
    assert exc.value.kind == "no_active_warning"


async def test_unwarn_returns_remaining_count(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    await service.warn(
        group=group, chat=CHAT, actor=actor, target=target, reason=None, settings=SETTINGS
    )
    assert await service.unwarn(group=group, actor=actor, target=target) == 0


async def test_kick_closes_open_restrictions(session):
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)
    await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=None, reason=None
    )
    await service.kick(group=group, chat=CHAT, actor=actor, target=target, reason="اخراج")
    restriction = (await session.execute(select(Restriction))).scalar_one()
    assert not restriction.is_active and restriction.end_reason == "kicked"


async def test_sync_external_closes_restriction_lifted_in_telegram(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=None, reason=None
    )
    await service.sync_external(group.id, target.id, "left")
    restriction = (await session.execute(select(Restriction))).scalar_one()
    assert not restriction.is_active and restriction.end_reason == "external"


async def test_user_info_reports_role_and_restrictions(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    await service.mute(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=3600, reason=None
    )
    info = await service.user_info(
        group=group, target=target, actor=actor, total_messages=12
    )
    assert info.role_key == "member"
    assert info.warning_count == 0
    assert [kind for kind, _ in info.restrictions] == ["mute"]
    assert info.total_messages == 12


async def test_admin_sync_feeds_role_lookup(session):
    group, actor, _ = await _setup(session)
    admins = AdminService(session)
    await admins.sync_admins(
        group.id,
        [
            AdminInfo(
                user=UserRef(platform="telegram", external_id=1, first_name="مدیر"),
                platform_role="creator",
                permissions={"can_restrict_members": True},
            )
        ],
    )
    assert await admins.get_role(group.id, actor.user.id) is HelliRole.OWNER


async def test_temporary_ban_is_released_after_its_duration(session):
    """مسدودی موقت پس از پایان مدت خودکار برداشته می‌شود و کاربر می‌تواند برگردد."""
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)
    await service.ban(
        group=group,
        chat=CHAT,
        actor=actor,
        target=target,
        duration_seconds=5 * 3600,
        reason="تبلیغ",
    )

    restriction = (await session.execute(select(Restriction))).scalar_one()
    restriction.until = utcnow() - timedelta(seconds=1)
    await session.flush()

    released = await service.release_expired_bans(group, CHAT)

    assert [user.external_id for user in released] == [target.external_id]
    assert ("unban", target.external_id, None) in adapter.calls
    assert not restriction.is_active and restriction.end_reason == "expired"
    actions = (await session.execute(select(ModerationAction))).scalars().all()
    assert actions[-1].action == "auto_unban"


async def test_permanent_ban_is_never_released_automatically(session):
    group, actor, target = await _setup(session)
    service = ModerationService(session, FakeAdapter())
    await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=None, reason=None
    )

    assert await service.release_expired_bans(group, CHAT) == []
    restriction = (await session.execute(select(Restriction))).scalar_one()
    assert restriction.is_active


async def test_permanent_ban_blocks_rejoining(session):
    """کاربری که مسدودی دائمی دارد، حتی با ورود دوباره اخراج می‌شود."""
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)
    await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=None, reason=None
    )
    adapter.banned.clear()  # شبیه‌سازی رفع مسدودی از منوی تلگرام

    assert await service.enforce_permanent_ban(group, CHAT, target) is True
    assert ("ban", target.external_id, None) in adapter.calls
    assert target.external_id in adapter.banned


async def test_temporary_ban_does_not_block_rejoining(session):
    group, actor, target = await _setup(session)
    adapter = FakeAdapter()
    service = ModerationService(session, adapter)
    await service.ban(
        group=group, chat=CHAT, actor=actor, target=target, duration_seconds=3600, reason=None
    )
    assert await service.enforce_permanent_ban(group, CHAT, target) is False
