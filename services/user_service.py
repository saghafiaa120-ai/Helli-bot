from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.repositories.users import UserRepository
from domain.dto import UserRef


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)

    async def upsert(self, ref: UserRef) -> User:
        """ثبت یا به‌روزرسانی اطلاعات نمایشی کاربر."""
        return await self._users.upsert(ref)

    async def get(self, platform: str, external_id: int) -> User | None:
        return await self._users.get(platform, external_id)

    async def find_by_username(self, platform: str, username: str) -> User | None:
        return await self._users.find_by_username(platform, username)

    async def get_or_create_by_id(self, platform: str, external_id: int) -> User:
        """کاربر را با شناسه می‌گیرد؛ اگر نبود فقط با شناسه می‌سازد (بدون دست زدن به نام‌ها)."""
        existing = await self._users.get(platform, external_id)
        if existing is not None:
            return existing
        return await self._users.upsert(UserRef(platform=platform, external_id=external_id))
