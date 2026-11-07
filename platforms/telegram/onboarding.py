"""همگام‌سازی اطلاعات گروه با تلگرام (مدیران، تعداد اعضا، دسترسی‌های ربات)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Group
from domain.dto import ChatRef
from platforms.base import PlatformAdapter, PlatformError
from services.admin_service import AdminService
from services.group_service import GroupService

logger = logging.getLogger(__name__)


async def refresh_group(
    session: AsyncSession,
    adapter: PlatformAdapter,
    group: Group,
    chat: ChatRef,
    *,
    refresh_bot_status: bool = False,
) -> None:
    """مدیران، تعداد اعضا و (در صورت نیاز) دسترسی‌های ربات را از پلتفرم می‌خواند.

    خطای API پلتفرم فقط لاگ می‌شود؛ مثلاً گروهی که ربات دیگر به آن دسترسی ندارد
    نباید پردازش بقیه رویدادها را متوقف کند.
    """
    groups = GroupService(session)

    try:
        admins = await adapter.get_admins(chat)
    except PlatformError as exc:
        logger.warning("Could not fetch admins for chat %s: %s", chat.external_id, exc)
    else:
        await AdminService(session).sync_admins(group.id, admins)

    try:
        await groups.set_member_count(group, await adapter.get_member_count(chat))
    except PlatformError as exc:
        logger.warning("Could not fetch member count for chat %s: %s", chat.external_id, exc)

    if refresh_bot_status:
        try:
            await groups.set_bot_status(group, await adapter.get_bot_status(chat))
        except PlatformError as exc:
            logger.warning("Could not fetch bot status for chat %s: %s", chat.external_id, exc)
