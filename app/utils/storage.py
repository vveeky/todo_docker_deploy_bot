# app/utils/storage.py

import datetime as dt
from typing import Any, Dict, List, Optional

from app.db.core import get_pool


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _dt_to_iso(value: Optional[dt.datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    else:
        value = value.astimezone(dt.timezone.utc)
    return value.replace(microsecond=0).isoformat()


def _parse_iso_to_dt(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        d = dt.datetime.fromisoformat(value)
    except Exception:
        return None
    # храним в БД как-aware UTC
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    else:
        d = d.astimezone(dt.timezone.utc)
    return d


async def _next_task_id(user_id: int) -> int:
    """
    Возвращает следующий task_id для пользователя (max+1).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(task_id) + 1, 1) AS next_id "
            "FROM task_state WHERE user_id = $1",
            user_id,
        )
    return int(row["next_id"])  # type: ignore[index]


# ---------- Публичные функции по задачам ----------


async def add_task(user_id: int, text: str) -> Dict[str, Any]:
    """
    Добавляет задачу в Postgres и возвращает её полное представление.
    """
    task_id = await _next_task_id(user_id)
    now = _now_utc()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO task_state (user_id, task_id, text, is_done, created_at, due_at)
            VALUES ($1, $2, $3, FALSE, $4, NULL)
            """,
            user_id,
            task_id,
            text,
            now,
        )

    return {
        "id": task_id,
        "text": text,
        "is_done": False,
        "created_at": _dt_to_iso(now),
        "due_at": None,
    }


async def list_user_tasks(user_id: int) -> List[Dict[str, Any]]:
    """
    Возвращает список задач пользователя из Postgres.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT task_id, text, is_done, created_at, due_at
            FROM task_state
            WHERE user_id = $1
            ORDER BY is_done, task_id
            """,
            user_id,
        )

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append(
            {
                "id": int(r["task_id"]),
                "text": str(r["text"] or ""),
                "is_done": bool(r["is_done"]),
                "created_at": _dt_to_iso(r["created_at"]),
                "due_at": _dt_to_iso(r["due_at"]),
            }
        )
    return result


async def get_task(task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Одна задача по user_id + task_id (id).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT task_id, text, is_done, created_at, due_at
            FROM task_state
            WHERE user_id = $1 AND task_id = $2
            """,
            user_id,
            task_id,
        )

    if not row:
        return None

    return {
        "id": int(row["task_id"]),
        "text": str(row["text"] or ""),
        "is_done": bool(row["is_done"]),
        "created_at": _dt_to_iso(row["created_at"]),
        "due_at": _dt_to_iso(row["due_at"]),
    }


_sentinel = object()


async def update_task(
    task_id: int,
    user_id: int,
    *,
    text: Optional[str] = None,
    is_done: Optional[bool] = None,
    due_at: Any = _sentinel,
) -> bool:
    """
    Обновляет задачу в Postgres.
    due_at:
      - строка ISO -> парсим и пишем в БД
      - None (передано явно) -> чистим дедлайн
      - _sentinel (по умолчанию) -> поле не трогаем
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_id, task_id
            FROM task_state
            WHERE user_id = $1 AND task_id = $2
            """,
            user_id,
            task_id,
        )
        if not row:
            return False

        sets: List[str] = []
        params: List[Any] = []
        idx = 1

        if text is not None:
            sets.append(f"text = ${idx}")
            params.append(text)
            idx += 1

        if is_done is not None:
            sets.append(f"is_done = ${idx}")
            params.append(bool(is_done))
            idx += 1

        if due_at is not _sentinel:
            if due_at is None:
                sets.append("due_at = NULL")
            else:
                dt_obj = (
                    _parse_iso_to_dt(due_at)
                    if isinstance(due_at, str)
                    else due_at
                )
                sets.append(f"due_at = ${idx}")
                params.append(dt_obj)
                idx += 1

        if not sets:
            return True

        params.append(user_id)
        params.append(task_id)

        sql = (
            "UPDATE task_state SET "
            + ", ".join(sets)
            + f" WHERE user_id = ${idx} AND task_id = ${idx + 1}"
        )

        result = await conn.execute(sql, *params)

    return result.endswith("UPDATE 1")


async def delete_task(task_id: int, user_id: int) -> bool:
    """
    Удаляет задачу из Postgres.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM task_state
            WHERE user_id = $1 AND task_id = $2
            """,
            user_id,
            task_id,
        )
    return result.endswith("DELETE 1")


async def set_due(task_id: int, user_id: int, due_iso: Optional[str]) -> bool:
    """
    Враппер для установки дедлайна по ISO-строке.
    """
    if due_iso is None:
        return await update_task(task_id, user_id, due_at=None)
    return await update_task(task_id, user_id, due_at=due_iso)


async def mark_done(task_id: int, user_id: int) -> bool:
    """
    Помечает задачу выполненной.
    """
    return await update_task(task_id, user_id, is_done=True)


async def list_due_tasks(until: dt.datetime) -> List[Dict[str, Any]]:
    """
    Список задач с установленным дедлайном.
    Параметр `until` сейчас не используется как фильтр,
    из-за небольшого масштаба просто выбираем все due != NULL,
    а реальную проверку окна делает is_due_now().
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, task_id, text, due_at
            FROM task_state
            WHERE due_at IS NOT NULL
            """,
        )

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append(
            {
                "user_id": int(r["user_id"]),
                "id": int(r["task_id"]),
                "text": str(r["text"] or ""),
                "due_at": _dt_to_iso(r["due_at"]),
            }
        )
    return result


async def clear_task_due(user_id: int, task_id: int) -> None:
    """
    Сбрасывает дедлайн у задачи.
    """
    await update_task(task_id, user_id, due_at=None)
