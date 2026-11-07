from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.repositories._utils import get_or_create
from domain.dto import UserRef


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, platform: str, external_id: int) -> User | None:
        stmt = select(User).where(User.platform == platform, User.external_id == external_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_many(self, user_ids: set[int]) -> dict[int, User]:
        if not user_ids:
            return {}
        stmt = select(User).where(User.id.in_(user_ids))
        return {user.id: user for user in (await self.session.execute(stmt)).scalars()}

    async def find_by_username(self, platform: str, username: str) -> User | None:
        """جست‌وجوی بدون حساسیت به حروف. اگر چند کاربر داشتند، جدیدترین فعالیت."""
        stmt = (
            select(User)
            .where(User.platform == platform, func.lower(User.username) == username.lower())
            .order_by(User.updated_at.desc(), User.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, ref: UserRef) -> User:
        """کاربر را می‌سازد یا اطلاعات نمایشی‌اش را در صورت تغییر به‌روز می‌کند."""
        user, created = await get_or_create(
            self.session,
            User,
            {"platform": ref.platform, "external_id": ref.external_id},
            {
                "username": ref.username,
                "first_name": ref.first_name,
                "last_name": ref.last_name,
                "language_code": ref.language_code,
                "is_bot": ref.is_bot,
            },
        )
        if created:
            return user

        changed = False
        for field in ("username", "first_name", "last_name", "language_code", "is_bot"):
            value = getattr(ref, field)
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if changed:
            await self.session.flush()
        return user
