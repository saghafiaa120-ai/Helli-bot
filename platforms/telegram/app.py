"""ساخت و اجرای ربات تلگرام."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, ErrorEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.texts_fa import BOT_COMMANDS, GROUP_COMMANDS
from platforms.telegram.adapter import TelegramAdapter
from platforms.telegram.confirmations import PendingConfirmations
from platforms.telegram.handlers import get_routers
from platforms.telegram.jobs import stats_jobs
from platforms.telegram.middlewares.db_session import DbSessionMiddleware
from platforms.telegram.middlewares.tracking import TrackingMiddleware
from platforms.telegram.resilience import is_transient
from services.message_counter import MessageCounter
from services.stats_service import flush_counter

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    """خطای پردازش را لاگ می‌کند تا ربات متوقف نشود.

    خطاهای گذرای شبکه (مثل قطع شدن اتصال به تلگرام) با سطح WARNING ثبت می‌شوند
    چون معمولاً خودبه‌خود برطرف می‌شوند و نیازی به بررسی ندارند.
    """
    exc = event.exception
    if is_transient(exc):
        logger.warning(
            "Transient error while processing update: %s: %s", type(exc).__name__, exc
        )
    else:
        logger.error("Unhandled error while processing update", exc_info=exc)

    # اگر خطا روی یک دکمه شیشه‌ای رخ داده باشد، باید پاسخ داده شود وگرنه
    # دکمه برای کاربر در حالت لودینگ می‌ماند.
    callback = event.update.callback_query
    if callback is not None:
        with suppress(Exception):
            await callback.answer()

    return True


def build_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
    adapter: TelegramAdapter,
    settings: Settings,
    counter: MessageCounter,
    pending: PendingConfirmations,
) -> Dispatcher:
    # آنچه به Dispatcher داده می‌شود، با همین نام‌ها در handlerها در دسترس است.
    # `config` تنظیمات برنامه است (نه تنظیمات گروه) تا نام `settings` آزاد بماند.
    dp = Dispatcher(adapter=adapter, config=settings, counter=counter, pending=pending)
    # نشست دیتابیس برای همه انواع رویداد؛ ثبت فعالیت و شمارش فقط برای پیام‌ها.
    # Outer middleware است تا حتی بدون handler مطابق هم اجرا شود.
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.message.outer_middleware(TrackingMiddleware(counter))
    for router in get_routers():
        dp.include_router(router)
    dp.errors.register(on_error)
    return dp


async def run_telegram(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> None:
    session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else None
    bot_kwargs = {"session": session} if session is not None else {}
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        **bot_kwargs,
    )
    adapter = TelegramAdapter(bot)
    counter = MessageCounter()
    dp = build_dispatcher(session_factory, adapter, settings, counter, PendingConfirmations())

    jobs = None
    try:
        me = await bot.get_me()
        logger.info("Bot started as @%s (id=%s)", me.username, me.id)
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in BOT_COMMANDS])
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in GROUP_COMMANDS],
            scope=BotCommandScopeAllGroupChats(),
        )
        jobs = asyncio.create_task(stats_jobs(session_factory, adapter, counter), name="stats-jobs")
        # شامل my_chat_member، chat_member و callback_query هم می‌شود چون handler دارند.
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if jobs is not None:
            jobs.cancel()
            with suppress(asyncio.CancelledError):
                await jobs
        try:
            # شمارش‌های ذخیره‌نشده را پیش از خاموش شدن می‌نویسیم.
            await flush_counter(session_factory, counter)
        except Exception:
            logger.exception("Final message-count flush failed")
        await bot.session.close()
