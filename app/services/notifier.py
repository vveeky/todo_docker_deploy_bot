# app/services/notifier.py
import asyncio
import datetime
import logging
from typing import List, Dict

from aiogram import Bot

from app.utils import storage
from app.utils import ui as ui_utils

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
    Фоновая петля. Периодически проверяет due и шлёт уведомления.
    Поведение:
      - получает due-задания через storage.list_due_tasks(until)
      - пытается перезаписать старый UI-экран (ui.show_notification)
        предполагая, что чат пользователя — это приватный чат с user_id.
        (Если у вас chat_id и user_id разные — см. комментарий ниже.)
      - сбрасывает дедлайн через storage.clear_task_due, чтобы задача
        не уведомлялась повторно.
    """
    logger.info("Notifier: запущен")
    try:
        while True:
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                due_tasks = await _get_due_tasks(now)

                if due_tasks:
                    logger.debug("Notifier: найдено %d задач для нотификации", len(due_tasks))

                for t in due_tasks:
                    user_id = int(t["user_id"])
                    task_id = int(t["id"])
                    text = str(t.get("text", "") or "")
                    due_at = t.get("due_at")  # ISO string

                    message_text = f"⏰ Напоминание: задача №{task_id}\n{text}"
                    if due_at:
                        message_text += f"\nДедлайн: {due_at}"

                    # Попытка аккуратно заменить UI-экран пользователя.
                    # Предполагаем приватный чат: chat_id == user_id.
                    chat_id = user_id

                    try:
                        await ui_utils.show_notification(bot, chat_id, user_id, message_text)
                    except Exception:
                        # fallback: отправить простое сообщение
                        try:
                            await bot.send_message(chat_id=chat_id, text=message_text)
                        except Exception:
                            logger.exception(
                                "Notifier: не удалось отправить уведомление user=%s task=%s",
                                user_id,
                                task_id,
                            )
                            # не сбрасываем дедлайн в случае ошибки отправки
                            continue

                    # после успешной отправки сбрасываем дедлайн, чтобы не дублировать
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
