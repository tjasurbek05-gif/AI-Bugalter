"""aiogram Bot + Dispatcher wiring: routers, FSM storage, scheduled jobs."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.handlers import expense, loan, payment, report
from app.handlers import settings as settings_handler
from app.handlers.loan import send_due_reminders
from app.utils.logger import get_logger
from config import settings

logger = get_logger(__name__)


def create_bot() -> Bot:
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)
    dp.include_router(settings_handler.router)
    dp.include_router(expense.router)
    dp.include_router(loan.router)
    dp.include_router(report.router)
    dp.include_router(payment.router)
    return dp


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(send_due_reminders, "cron", hour=9, minute=0, args=[bot], id="loan_reminders")
    return scheduler


async def _polling_main() -> None:
    """Local/dev entrypoint: `python bot.py` runs long polling (no public webhook needed)."""
    bot = create_bot()
    dp = create_dispatcher()
    scheduler = create_scheduler(bot)
    scheduler.start()

    logger.info("bot_starting_polling")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_polling_main())
