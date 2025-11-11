# app/services/notifier.py
import asyncio
import datetime
import logging
from typing import List, Dict

from aiogram import Bot

from app.utils import storage
from app.utils import ui as ui_utils
from app.utils.timezone import is_due_now

logger = logging.getLogger(__name__)


async def _get_due_tasks(until: datetime.datetime) -> List[Dict]:
    """
    Возвращает список задач, у которых due_at <= until.
    Использует storage.list_due_tasks(until).
    """
    try:
        return await storage.list_due_tasks(until)
    except Exception:
        logger.exception("Notifier: ошибка при получении задач")
        return []


async def notifier(bot: Bot, interval_seconds: int = 30) -> None:
    """
    Цикл: проверяем due, отправляем новое уведомление с кнопкой 'список команд',
    забываем ui_state (message_id), дедлайн сбрасываем.
    """
    logger.info("Notifier: запущен")
    try:
        while True:
            try:
                now = datetime.datetime.now()
                due_tasks = await _get_due_tasks(now)

                if due_tasks:
                    logger.debug(
                        "Notifier: найдено %d задач для проверки нотификации",
                        len(due_tasks),
                    )

                for t in due_tasks:
                    user_id = int(t["user_id"])
                    task_id = int(t["id"])
                    text = str(t.get("text", "") or "")
                    due_at = t.get("due_at")  # ISO локального времени пользователя

                    # дедлайн наступил с учётом tz_offset?
                    if not await is_due_now(user_id, due_at, now=now):
                        continue

                    message_text = f"⏰ Напоминание: задача №{task_id}\n{text}"
                    if due_at:
                        message_text += f"\nДедлайн: {due_at}"

                    # отправляем уведомление, не трогая ui_state
                    try:
                        await ui_utils.show_notification(
                            bot=bot,
                            chat_id=user_id,
                            user_id=user_id,
                            text=message_text,
                        )
                    except Exception:
                        logger.exception(
                            "Notifier: не удалось отправить уведомление user=%s task=%s",
                            user_id,
                            task_id,
                        )
                        # не сбрасываем due, попробуем позже
                        continue

                    # сбрасываем дедлайн, чтобы не дублировать уведомление
                    try:
                        await storage.clear_task_due(user_id, task_id)
                    except Exception:
                        logger.exception(
                            "Notifier: ошибка при сбросе дедлайна user=%s task=%s",
                            user_id,
                            task_id,
                        )

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Notifier: неожиданная ошибка в цикле")
                await asyncio.sleep(10)
    finally:
        logger.info("Notifier: завершён")
