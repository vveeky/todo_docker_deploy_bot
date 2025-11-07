# app/services/notifier.py
import asyncio
import datetime as dt
import logging
from typing import List, Dict, Any

from aiogram import Bot

from app.utils import storage
from app.utils.dates import format_dt

logger = logging.getLogger(__name__)


async def _get_due_tasks(now: dt.datetime) -> List[Dict[str, Any]]:
    """Вернёт список задач, у которых due_at <= now и is_done == 0."""
    tasks = await storage.list_tasks()
    result: List[Dict[str, Any]] = []

    for t in tasks:
        if t.get("is_done"):
            continue
        due_at = t.get("due_at")
        if not due_at:
            continue
        try:
            due_dt = dt.datetime.fromisoformat(due_at)
        except Exception:
            logger.warning("Notifier: некорректный due_at у задачи %r", t)
            continue
        if due_dt <= now:
            result.append(t)

    return result


async def notifier(bot: Bot, interval: int = 60) -> None:
    """
    Фоновый цикл:
    - раз в interval секунд смотрит на due_at;
    - если дедлайн прошёл, шлёт уведомление;
    - после отправки сбрасывает due_at, чтобы не спамить.
    """
    logger.info("Notifier стартует с interval=%s сек", interval)

    await asyncio.sleep(2)

    while True:
        now = dt.datetime.now().replace(second=0, microsecond=0)

        try:
            due_tasks = await _get_due_tasks(now)
        except Exception:
            logger.exception("Notifier: ошибка при получении задач")
            due_tasks = []

        if due_tasks:
            logger.info(
                "Notifier: найдено %s задач(и) с дедлайном <= %s",
                len(due_tasks),
                now.isoformat(),
            )

        for t in due_tasks:
            user_id = t.get("user_id")
            text = t.get("text", "")
            due_at = t.get("due_at")

            if not user_id:
                logger.warning("Notifier: задача без user_id: %r", t)
                continue

            msg = f"Напоминание по задаче #{t['id']}: {text}\nВремя: {format_dt(due_at)}"
            try:
                await bot.send_message(chat_id=user_id, text=msg)
                logger.info(
                    "Notifier: отправлено напоминание для user_id=%s, task_id=%s",
                    user_id,
                    t.get("id"),
                )
            except Exception:
                logger.exception(
                    "Notifier: ошибка при отправке напоминания для user_id=%s, task_id=%s",
                    user_id,
                    t.get("id"),
                )
                continue

            try:
                await storage.update_task(t["id"], user_id, due_at=None)
                logger.debug(
                    "Notifier: сброшен due_at у задачи task_id=%s", t.get("id")
                )
            except Exception:
                logger.exception(
                    "Notifier: не удалось обновить задачу после отправки, task_id=%s",
                    t.get("id"),
                )

        await asyncio.sleep(interval)