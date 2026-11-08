"""منطق مدیریت کاربران: مسدود، سکوت، اخراج، اخطار و اطلاعات کاربر.

همه بررسی‌های مجوز این‌جا انجام می‌شود تا handlerها فقط ورودی را به سرویس بدهند
و متن پاسخ را بسازند. خطاهای قابل نمایش به کاربر با `ModerationError` بالا
می‌روند و handler آن را به متن فارسی تبدیل می‌کند.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import (
    EndReason,
    HelliRole,
    ModerationActionType,
    RestrictionType,
)
from core.permissions import Permission, role_has_permission
from core.timeutils import utcnow
from database.models import Group, User, Warning
from database.repositories.members import MemberRepository
from database.repositories.moderation import (
    ModerationActionRepository,
    RestrictionRepository,
)
from database.repositories.users import UserRepository
from database.repositories.warnings import WarningRepository
from domain.dto import ChatRef, ModerationSettings
from platforms.base import PlatformAdapter, PlatformError
from services.admin_service import AdminService

logger = logging.getLogger(__name__)

AUTO_MUTE_REASON = "رسیدن اخطارها به سقف"
AUTO_UNBAN_REASON = "پایان مدت مسدودی موقت"
PERMANENT_BAN_REASON = "مسدودی دائمی (بازگشت مسدود)"


class ModerationError(Exception):
    """خطای قابل نمایش؛ `kind` نوع پیام مناسب را مشخص می‌کند."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class Actor:
    """کسی که دستور را اجرا می‌کند (مدیر گروه یا مالک ربات)."""

    user: User
    role: HelliRole | None = None
    is_global_owner: bool = False
    permissions: dict[str, bool] = field(default_factory=dict)

    @property
    def external_id(self) -> int:
        return self.user.external_id

    def can(self, permission: Permission) -> bool:
        if self.is_global_owner:
            return True
        return role_has_permission(self.role, permission)

    def has_platform_permission(self, key: str) -> bool:
        """دسترسی اعلام‌شده توسط خود پلتفرم (مثلاً can_restrict_members)."""
        if self.is_global_owner:
            return True
        return bool(self.permissions.get(key, False))


@dataclass(frozen=True, slots=True)
class RestrictionOutcome:
    until: datetime | None
    duration_seconds: int | None


@dataclass(frozen=True, slots=True)
class WarnOutcome:
    count: int
    limit: int
    auto_mute_seconds: int | None = None
    auto_mute_until: datetime | None = None
    auto_mute_failed: bool = False


@dataclass(frozen=True, slots=True)
class UserInfo:
    """داده‌های کارت «اطلاعات کاربر»."""

    user: User
    role_key: str
    member_status: str | None
    warning_count: int
    restrictions: tuple[tuple[str, datetime | None], ...] = ()
    first_seen: datetime | None = None
    joined_at: datetime | None = None
    last_active: datetime | None = None
    total_messages: int = 0


class ModerationService:
    def __init__(self, session: AsyncSession, adapter: PlatformAdapter) -> None:
        self._session = session
        self._adapter = adapter
        self._restrictions = RestrictionRepository(session)
        self._warnings = WarningRepository(session)
        self._actions = ModerationActionRepository(session)
        self._members = MemberRepository(session)
        self._users = UserRepository(session)
        self._admins = AdminService(session)

    # ----- بررسی مجوزها ---------------------------------------------------------

    async def _ensure_moderator(self, group: Group, actor: Actor) -> None:
        """نقش داخلی کاربر باید اجازه مدیریت کاربران را بدهد."""
        if not actor.can(Permission.MODERATE_USERS):
            raise ModerationError("not_authorized")

    async def _ensure_can_moderate(self, group: Group, actor: Actor, target: User) -> None:
        """بررسی‌های مشترک همه اقدامات: هدف، نقش و دسترسی پلتفرم."""
        await self._ensure_moderator(group, actor)

        if target.id == actor.user.id:
            raise ModerationError("cannot_target_self")
        if target.external_id == self._adapter.bot_user_id:
            raise ModerationError("cannot_target_bot")
        if await self._admins.get_role(group.id, target.id) is not None:
            raise ModerationError("cannot_target_admin")
        if not actor.has_platform_permission("can_restrict_members"):
            raise ModerationError("missing_platform_permission")

    @staticmethod
    def _until(duration_seconds: int | None) -> datetime | None:
        if duration_seconds is None:
            return None
        return utcnow() + timedelta(seconds=duration_seconds)

    async def _record(
        self,
        group: Group,
        actor: Actor,
        target: User,
        action: ModerationActionType,
        *,
        duration_seconds: int | None = None,
        reason: str | None = None,
    ) -> None:
        await self._actions.add(
            action.value,
            group_id=group.id,
            actor_user_id=actor.user.id,
            target_user_id=target.id,
            duration_seconds=duration_seconds,
            reason=reason,
        )

    # ----- اقدامات ---------------------------------------------------------------

    async def ban(
        self,
        *,
        group: Group,
        chat: ChatRef,
        actor: Actor,
        target: User,
        duration_seconds: int | None,
        reason: str | None,
    ) -> RestrictionOutcome:
        await self._ensure_can_moderate(group, actor, target)
        until = self._until(duration_seconds)
        try:
            await self._adapter.ban_member(chat, target.external_id, until)
        except PlatformError as exc:
            raise ModerationError(exc.kind) from exc

        await self._restrictions.end_active(
            group.id, target.id, RestrictionType.BAN.value, EndReason.REPLACED.value
        )
        await self._restrictions.add(
            group.id,
            target.id,
            RestrictionType.BAN.value,
            until=until,
            reason=reason,
            created_by_user_id=actor.user.id,
        )
        await self._record(
            group,
            actor,
            target,
            ModerationActionType.BAN,
            duration_seconds=duration_seconds,
            reason=reason,
        )
        return RestrictionOutcome(until=until, duration_seconds=duration_seconds)

    async def unban(
        self, *, group: Group, chat: ChatRef, actor: Actor, target: User
    ) -> bool:
        """رفع مسدودی. اگر کاربر مسدود نبود False برمی‌گرداند."""
        await self._ensure_can_moderate(group, actor, target)
        try:
            lifted = await self._adapter.unban_member(chat, target.external_id)
        except PlatformError as exc:
            raise ModerationError(exc.kind) from exc

        ended = await self._restrictions.end_active(
            group.id, target.id, RestrictionType.BAN.value, EndReason.MANUAL.value
        )
        if lifted or ended:
            await self._record(group, actor, target, ModerationActionType.UNBAN)
        return bool(lifted or ended)

    # ----- آزادسازی خودکار و مسدودی دائمی ---------------------------------------

    async def release_expired_bans(self, group: Group, chat: ChatRef) -> list[User]:
        """مسدودی‌های موقتی که مدتشان تمام شده را برمی‌دارد تا کاربر بتواند برگردد.

        خروجی: کاربرانی که آزاد شدند (برای اعلام در گروه).
        """
        released: list[User] = []
        for row in await self._restrictions.list_due(RestrictionType.BAN.value, group.id):
            target = await self._session.get(User, row.user_id)
            await self._restrictions.end(row, EndReason.EXPIRED.value)
            if target is None:
                continue
            try:
                await self._adapter.unban_member(chat, target.external_id)
            except PlatformError as exc:
                # کاربر ممکن است دیگر عضو نباشد؛ بقیه خطاها فقط لاگ می‌شوند.
                if exc.kind != "not_found":
                    logger.warning("Auto unban failed for %s: %s", target.external_id, exc)
            await self._actions.add(
                ModerationActionType.AUTO_UNBAN.value,
                group_id=group.id,
                target_user_id=target.id,
                reason=AUTO_UNBAN_REASON,
            )
            released.append(target)
        return released

    async def enforce_permanent_ban(
        self, group: Group, chat: ChatRef, target: User
    ) -> bool:
        """اگر کاربر مسدودی دائمی فعال دارد، هنگام تلاش برای بازگشت دوباره مسدود می‌شود.

        مسدودی دائمی هرگز خودبه‌خود برداشته نمی‌شود؛ فقط `/unban` آن را لغو می‌کند.
        """
        active = await self._restrictions.get_active(
            group.id, target.id, RestrictionType.BAN.value
        )
        if active is None or active.until is not None:
            return False
        try:
            await self._adapter.ban_member(chat, target.external_id, None)
        except PlatformError as exc:
            logger.warning(
                "Could not re-apply permanent ban for %s: %s", target.external_id, exc
            )
            return False
        await self._actions.add(
            ModerationActionType.BAN.value,
            group_id=group.id,
            target_user_id=target.id,
            reason=PERMANENT_BAN_REASON,
        )
        return True

    async def mute(
        self,
        *,
        group: Group,
        chat: ChatRef,
        actor: Actor,
        target: User,
        duration_seconds: int | None,
        reason: str | None,
    ) -> RestrictionOutcome:
        await self._ensure_can_moderate(group, actor, target)
        until = self._until(duration_seconds)
        try:
            await self._adapter.mute_member(chat, target.external_id, until)
        except PlatformError as exc:
            raise ModerationError(exc.kind) from exc

        await self._restrictions.end_active(
            group.id, target.id, RestrictionType.MUTE.value, EndReason.REPLACED.value
        )
        await self._restrictions.add(
            group.id,
            target.id,
            RestrictionType.MUTE.value,
            until=until,
            reason=reason,
            created_by_user_id=actor.user.id,
        )
        await self._record(
            group,
            actor,
            target,
            ModerationActionType.MUTE,
            duration_seconds=duration_seconds,
            reason=reason,
        )
        return RestrictionOutcome(until=until, duration_seconds=duration_seconds)

    async def unmute(
        self, *, group: Group, chat: ChatRef, actor: Actor, target: User
    ) -> bool:
        await self._ensure_can_moderate(group, actor, target)
        try:
            lifted = await self._adapter.unmute_member(chat, target.external_id)
        except PlatformError as exc:
            raise ModerationError(exc.kind) from exc

        ended = await self._restrictions.end_active(
            group.id, target.id, RestrictionType.MUTE.value, EndReason.MANUAL.value
        )
        if lifted or ended:
            await self._record(group, actor, target, ModerationActionType.UNMUTE)
        return bool(lifted or ended)

    async def kick(
        self,
        *,
        group: Group,
        chat: ChatRef,
        actor: Actor,
        target: User,
        reason: str | None,
    ) -> None:
        await self._ensure_can_moderate(group, actor, target)
        try:
            await self._adapter.kick_member(chat, target.external_id)
        except PlatformError as exc:
            raise ModerationError(exc.kind) from exc

        for kind in (RestrictionType.BAN.value, RestrictionType.MUTE.value):
            await self._restrictions.end_active(group.id, target.id, kind, EndReason.KICKED.value)
        await self._record(group, actor, target, ModerationActionType.KICK, reason=reason)

    async def warn(
        self,
        *,
        group: Group,
        chat: ChatRef,
        actor: Actor,
        target: User,
        reason: str | None,
        settings: ModerationSettings,
    ) -> WarnOutcome:
        await self._ensure_can_moderate(group, actor, target)
        await self._warnings.add(
            group.id, target.id, actor_user_id=actor.user.id, reason=reason
        )
        count = await self._warnings.count_active(group.id, target.id)
        await self._record(group, actor, target, ModerationActionType.WARN, reason=reason)

        limit = settings.warn_limit
        outcome = WarnOutcome(count=count, limit=limit)
        if limit <= 0 or count < limit:
            return outcome

        # سقف اخطار: سکوت موقت و صفر کردن شمارنده. هرگز مسدودی خودکار اعمال نمی‌شود.
        seconds = settings.warn_mute_seconds
        until = self._until(seconds)
        try:
            await self._adapter.mute_member(chat, target.external_id, until)
        except PlatformError as exc:
            logger.warning("Auto-mute after warn limit failed: %s", exc)
            return WarnOutcome(count=count, limit=limit, auto_mute_failed=True)

        await self._restrictions.end_active(
            group.id, target.id, RestrictionType.MUTE.value, EndReason.REPLACED.value
        )
        await self._restrictions.add(
            group.id,
            target.id,
            RestrictionType.MUTE.value,
            until=until,
            reason=AUTO_MUTE_REASON,
            created_by_user_id=actor.user.id,
        )
        await self._warnings.revoke_all(
            group.id,
            target.id,
            revoked_by_user_id=actor.user.id,
            reason=EndReason.LIMIT.value,
        )
        await self._record(
            group,
            actor,
            target,
            ModerationActionType.MUTE,
            duration_seconds=seconds,
            reason=AUTO_MUTE_REASON,
        )
        return WarnOutcome(
            count=count, limit=limit, auto_mute_seconds=seconds, auto_mute_until=until
        )

    async def unwarn(
        self, *, group: Group, actor: Actor, target: User
    ) -> int:
        """آخرین اخطار فعال را لغو می‌کند و تعداد باقی‌مانده را برمی‌گرداند."""
        await self._ensure_moderator(group, actor)
        active = await self._warnings.list_active(group.id, target.id)
        if not active:
            raise ModerationError("no_active_warning")
        await self._warnings.revoke(
            active[0], revoked_by_user_id=actor.user.id, reason=EndReason.MANUAL.value
        )
        await self._record(group, actor, target, ModerationActionType.UNWARN)
        return len(active) - 1

    # ----- خواندن اطلاعات ---------------------------------------------------------

    async def user_info(
        self,
        *,
        group: Group,
        target: User,
        actor: Actor,
        total_messages: int = 0,
    ) -> UserInfo:
        """اطلاعات کاربر برای کارت `/info`."""
        if target.id != actor.user.id:
            await self._ensure_moderator(group, actor)

        admin_row = await self._admins.get_admin(group.id, target.id)
        if admin_row is None:
            role_key = "member"
        elif admin_row.platform_role:
            role_key = admin_row.platform_role  # creator | admin
        else:
            role_key = admin_row.helli_role  # moderator

        member = await self._members.get(group.id, target.id)
        active = await self._restrictions.list_active(group.id, target.id)
        count = await self._warnings.count_active(group.id, target.id)
        return UserInfo(
            user=target,
            role_key=role_key,
            member_status=member.status if member else None,
            warning_count=count,
            restrictions=tuple((row.kind, row.until) for row in active),
            first_seen=target.created_at,
            joined_at=member.joined_at if member else None,
            last_active=member.last_active_at if member else None,
            total_messages=total_messages,
        )

    async def warning_history(
        self, group: Group, target: User, limit: int = 10
    ) -> tuple[int, list[tuple[Warning, str]]]:
        """(تعداد اخطارهای فعال، فهرست (اخطار، نام صادرکننده))."""
        rows = await self._warnings.list_recent(group.id, target.id, limit)
        count = await self._warnings.count_active(group.id, target.id)
        actor_ids = {row.actor_user_id for row in rows if row.actor_user_id}
        names = {
            user_id: " ".join(
                part for part in (user.first_name, user.last_name) if part
            ).strip()
            or (f"@{user.username}" if user.username else str(user.external_id))
            for user_id, user in (await self._users.get_many(actor_ids)).items()
        }
        return count, [
            (row, names.get(row.actor_user_id or 0, "ناشناس")) for row in rows
        ]

    # ----- هم‌گام‌سازی با تغییرات بیرونی ---------------------------------------------

    async def sync_external(self, group_id: int, user_id: int, platform_status: str) -> None:
        """اگر مدیری از منوی خود تلگرام کاربری را آزاد/محدود کرد، سوابق ربات را هم‌گام می‌کند."""
        if platform_status != "kicked":
            ended = await self._restrictions.end_active(
                group_id, user_id, RestrictionType.BAN.value, EndReason.EXTERNAL.value
            )
            if ended:
                logger.info("Ban lifted outside the bot (group=%s user=%s)", group_id, user_id)
        if platform_status != "restricted":
            ended = await self._restrictions.end_active(
                group_id, user_id, RestrictionType.MUTE.value, EndReason.EXTERNAL.value
            )
            if ended:
                logger.info("Mute lifted outside the bot (group=%s user=%s)", group_id, user_id)
