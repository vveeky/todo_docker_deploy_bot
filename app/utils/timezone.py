# app/utils/timezone.py
import datetime as dt
from typing import Optional

from app.db.core import get_user_tz_offset


async def to_server_due_dt(
    user_id: int,
    due_at_str: Optional[str],
) -> Optional[dt.datetime]:
    """
    Преобразует локальный дедлайн пользователя (ISO-строка) в серверное время.

    tz_offset_minutes хранится как (server - user) в минутах.
    Серверное время дедлайна = локальное + offset.
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
    user_id: int,
    due_at_str: Optional[str],
    now: Optional[dt.datetime] = None,
    window_seconds: int = 90,
) -> bool:
    """
    True, если дедлайн (локальный у пользователя) уже наступил
    с учётом tz_offset_minutes.

    Проверяем окно [server_due, server_due + window_seconds].
    """
    if now is None:
        now = dt.datetime.now()

    server_due = await to_server_due_dt(user_id, due_at_str)
    if server_due is None:
        return False

    # Приводим оба datetime к наивным (без tzinfo), чтобы избежать
    # TypeError: can't subtract offset-naive and offset-aware datetimes
    if server_due.tzinfo is not None:
        server_due = server_due.astimezone(dt.timezone.utc).replace(tzinfo=None)
    if now.tzinfo is not None:
        now = now.astimezone(dt.timezone.utc).replace(tzinfo=None)

    delta = (now - server_due).total_seconds()
    return 0 <= delta <= window_seconds