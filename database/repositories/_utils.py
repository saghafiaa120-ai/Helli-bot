from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


async def get_or_create(
    session: AsyncSession,
    model: type[ModelT],
    lookup: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> tuple[ModelT, bool]:
    """رکورد را می‌گیرد یا می‌سازد؛ در برابر ساخت هم‌زمان (Race) امن است.

    ساخت داخل SAVEPOINT انجام می‌شود تا اگر هم‌زمان رکورد دیگری با همان کلید یکتا
    ساخته شده بود، فقط همین بخش برگردد و رکورد موجود خوانده شود.
    """
    stmt = select(model).filter_by(**lookup)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    obj = model(**lookup, **(defaults or {}))
    try:
        async with session.begin_nested():
            session.add(obj)
            await session.flush()
    except IntegrityError:
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            raise
        return existing, False
    return obj, True
