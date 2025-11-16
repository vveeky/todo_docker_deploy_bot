# app/utils/timezone.py
import datetime as dt
from typing import Optional

from app.db.core import get_user_tz_offset


async def to_server_due_dt(
    user_id: int,
    due_at_str: Optional[str],
) -> Optional[dt.datetime]:
    """
    СТАРАЯ логика: интерпретация локального дедлайна пользователя как server = local + offset.
    Сейчас в коде больше не используется, оставлена только на случай,
    если где-то ещё будет нужна.
    """
    if not due_at_str:
        return None

    try:
        local_dt = dt.datetime.fromisoformat(due_at_str)
    except Exception:
        return None

    offset = await get_user_tz_offset(user_id)
    if offset is None:
        offset = 0

    return local_dt + dt.timedelta(minutes=offset)


async def is_due_now(
    user_id: int,  # параметр оставляем для совместимости сигнатуры
    due_at_str: Optional[str],
    now: Optional[dt.datetime] = None,
    window_seconds: int = 90,
) -> bool:
    """
    True, если дедлайн уже наступил.

    ВАЖНО: сейчас due_at хранится в БД в UTC (TIMESTAMPTZ),
    а storage.list_due_tasks() возвращает ISO-строку в UTC.

    Поэтому здесь:
    - парсим ISO как UTC,
    - сравниваем с текущим временем в UTC,
    - ничего не делаем с tz_offset.
    """
    if not due_at_str:
        return False

    # now приводим к aware UTC
    if now is None:
        now_utc = dt.datetime.now(dt.timezone.utc)
    else:
        if now.tzinfo is None:
            now_utc = now.replace(tzinfo=dt.timezone.utc)
        else:
            now_utc = now.astimezone(dt.timezone.utc)

    # due_at_str -> aware UTC
    try:
        d = dt.datetime.fromisoformat(due_at_str)
    except Exception:
        return False

    if d.tzinfo is None:
        due_utc = d.replace(tzinfo=dt.timezone.utc)
    else:
        due_utc = d.astimezone(dt.timezone.utc)

    delta = (now_utc - due_utc).total_seconds()
    return 0 <= delta <= window_seconds