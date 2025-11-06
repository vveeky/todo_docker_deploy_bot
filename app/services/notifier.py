# app/services/notifier.py
import asyncio
import datetime as dt
from typing import List, Dict, Any

from aiogram import Bot

from app.utils import storage


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

    # можно сделать маленькую задержку перед первым проходом
    await asyncio.sleep(2)

    while True:
        now = dt.datetime.now().replace(second=0, microsecond=0)

        due_tasks = await _get_due_tasks(now)
        for t in due_tasks:
            user_id = t.get("user_id")
            text = t.get("text", "")
            due_at = t.get("due_at")

            if not user_id:
                continue

            msg = f"Напоминание по задаче #{t['id']}: {text}\nВремя: {due_at}"
            try:
                await bot.send_message(chat_id=user_id, text=msg)
            except Exception as e:
                # можно заменить на логгер, сейчас просто print
                print(f"[notifier] send_message error: {e}")

            # сбросить due_at, чтобы не напоминать повторно
            await storage.update_task(t["id"], user_id, due_at=None)

        await asyncio.sleep(interval)
