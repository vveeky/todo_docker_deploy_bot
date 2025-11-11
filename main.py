# main.py
import asyncio
import logging

from config.config import load_config, Config
from app.bot import bot, dp
from app.handlers.start import start_router
from app.handlers.todo import todo_router
from app.services.notifier import notifier

from app.db.core import init_db_and_schema


logger = logging.getLogger(__name__)


async def main():
    config: Config = load_config()
    await init_db_and_schema()

    logging.basicConfig(
        level=logging.getLevelName(config.log.level),
        format=config.log.format,
    )
    logger.info("Starting bot")

    dp.include_router(start_router)
    dp.include_router(todo_router)

    asyncio.create_task(notifier(bot, interval_seconds=30))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
