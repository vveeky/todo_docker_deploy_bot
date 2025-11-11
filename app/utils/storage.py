# app/utils/storage.py
import asyncio
import json
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db.core import get_pool

# JSON только для id и текста
TASKS_FILE = (
    Path(__file__).resolve().parent.parent.parent / "data" / "tasks.json"
)

_file_lock = asyncio.Lock()


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def _load_raw_json() -> Dict[str, Any]:
    """
    Читает JSON без блокировки. Для read-only операций ок.
    """
    if not TASKS_FILE.exists():
        return {}
    text = await asyncio.to_thread(TASKS_FILE.read_text, encoding="utf-8")
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        return data
    except json.JSONDecodeError:
        return {}


async def _load_json_locked() -> Dict[str, Any]:
    """
    Чтение JSON под локом — для операций, которые будут писать файл.
    """
    async with _file_lock:
        if not TASKS_FILE.exists():
            return {}
        text = await asyncio.to_thread(TASKS_FILE.read_text, encoding="utf-8")
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                return {}
            return data
        except json.JSONDecodeError:
            return {}


async def _save_json_locked(data: Dict[str, Any]) -> None:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    dump = json.dumps(data, ensure_ascii=False, indent=2)
    async with _file_lock:
        await asyncio.to_thread(TASKS_FILE.write_text, dump, encoding="utf-8")


def _ensure_user_block(data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    key = str(user_id)
    block = data.get(key)
    if not isinstance(block, dict):
        block = {"next_id": 1, "tasks": []}
        data[key] = block

    if "next_id" not in block or not isinstance(block["next_id"], int):
        block["next_id"] = 1
    if "tasks" not in block or not isinstance(block["tasks"], list):
        block["tasks"] = []

    return block


def _find_task_in_block(
    block: Dict[str, Any], task_id: int
) -> Optional[Dict[str, Any]]:
    for t in block.get("tasks", []):
        if int(t.get("id", -1)) == task_id:
            return t
    return None


def _parse_iso_to_dt(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        d = dt.datetime.fromisoformat(value)
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    else:
        d = d.astimezone(dt.timezone.utc)
    return d


def _dt_to_iso(value: Optional[dt.datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    else:
        value = value.astimezone(dt.timezone.utc)
    return value.replace(microsecond=0).isoformat()


# ---------- Публичные функции по задачам ----------


async def add_task(user_id: int, text: str) -> Dict[str, Any]:
    """
    Добавляет задачу:
    - в JSON кладёт (id, text)
    - в Postgres создаёт запись состояния (is_done, created_at, due_at)
    """
    # сначала JSON
    data = await _load_json_locked()
    block = _ensure_user_block(data, user_id)

    task_id = int(block["next_id"])
    block["next_id"] = task_id + 1
    block["tasks"].append({"id": task_id, "text": text})
    await _save_json_locked(data)

    # затем состояние в БД
    pool = await get_pool()
    now = _now_utc()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO task_state (user_id, task_id, is_done, created_at, due_at)
            VALUES ($1, $2, FALSE, $3, NULL)
            ON CONFLICT (user_id, task_id) DO NOTHING
            """,
            user_id,
            task_id,
            now,
        )

    # вернуть объединённую задачу
    return await get_task(task_id, user_id)


async def list_user_tasks(user_id: int) -> List[Dict[str, Any]]:
    """
    Возвращает список задач пользователя:
    - text и id из JSON
    - is_done, created_at, due_at из Postgres (если нет — дефолты)
    """
    data = await _load_raw_json()
    block = data.get(str(user_id)) or {}
    tasks_json = block.get("tasks") or []

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT task_id, is_done, created_at, due_at
            FROM task_state
            WHERE user_id = $1
            """,
            user_id,
        )

    state_by_id: Dict[int, Any] = {
        int(r["task_id"]): r for r in rows  # type: ignore[index]
    }

    result: List[Dict[str, Any]] = []
    for t in tasks_json:
        tid = int(t.get("id", -1))
        text = str(t.get("text", ""))

        s = state_by_id.get(tid)
        if s:
            is_done = bool(s["is_done"])
            created_at = _dt_to_iso(s["created_at"])
            due_at = _dt_to_iso(s["due_at"])
        else:
            is_done = False
            created_at = _dt_to_iso(_now_utc())
            due_at = None

        result.append(
            {
                "id": tid,
                "text": text,
                "is_done": is_done,
                "created_at": created_at,
                "due_at": due_at,
            }
        )

    return result


async def get_task(task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Одна задача по user_id + task_id (id).
    """
    data = await _load_raw_json()
    block = data.get(str(user_id))
    if not isinstance(block, dict):
        return None

    base = _find_task_in_block(block, task_id)
    if not base:
        return None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT is_done, created_at, due_at
            FROM task_state
            WHERE user_id = $1 AND task_id = $2
            """,
            user_id,
            task_id,
        )

    if row:
        is_done = bool(row["is_done"])
        created_at = _dt_to_iso(row["created_at"])
        due_at = _dt_to_iso(row["due_at"])
    else:
        is_done = False
        created_at = _dt_to_iso(_now_utc())
        due_at = None

    return {
        "id": int(base["id"]),
        "text": str(base["text"]),
        "is_done": is_done,
        "created_at": created_at,
        "due_at": due_at,
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
    Обновляет задачу.
    - text -> JSON
    - is_done/due_at -> Postgres

    due_at:
      - строка ISO -> парсим и пишем в БД
      - None (передано явно) -> чистим дедлайн
      - _sentinel (по умолчанию) -> поле не трогаем
    """
    # текст в JSON
    if text is not None:
        data = await _load_json_locked()
        block = _ensure_user_block(data, user_id)
        task = _find_task_in_block(block, task_id)
        if not task:
            # нет такой задачи
            await _save_json_locked(data)
            return False
        task["text"] = text
        await _save_json_locked(data)

    # состояние в БД
    pool = await get_pool()
    async with pool.acquire() as conn:
        # нужно убедиться, что запись есть
        row = await conn.fetchrow(
            """
            SELECT user_id, task_id, is_done, created_at, due_at
            FROM task_state
            WHERE user_id = $1 AND task_id = $2
            """,
            user_id,
            task_id,
        )
        if not row:
            # создаём строку по умолчанию
            await conn.execute(
                """
                INSERT INTO task_state (user_id, task_id, is_done, created_at, due_at)
                VALUES ($1, $2, FALSE, $3, NULL)
                ON CONFLICT (user_id, task_id) DO NOTHING
                """,
                user_id,
                task_id,
                _now_utc(),
            )

        # собираем поля для апдейта
        sets = []
        params: List[Any] = []
        idx = 1

        if is_done is not None:
            sets.append(f"is_done = ${idx}")
            params.append(bool(is_done))
            idx += 1

        if due_at is not _sentinel:
            if due_at is None:
                sets.append(f"due_at = NULL")
            else:
                dt_obj = (
                    _parse_iso_to_dt(due_at)
                    if isinstance(due_at, str)
                    else None
                )
                sets.append(f"due_at = ${idx}")
                params.append(dt_obj)
                idx += 1

        if not sets:
            return True  # нечего менять

        # user_id, task_id в конец параметров
        params.append(user_id)
        params.append(task_id)

        sql = (
            "UPDATE task_state SET "
            + ", ".join(sets)
            + " WHERE user_id = $"
            + str(idx)
            + " AND task_id = $"
            + str(idx + 1)
        )

        await conn.execute(sql, *params)

    return True


async def delete_task(task_id: int, user_id: int) -> bool:
    """
    Удаляет задачу и из JSON, и из Postgres.
    """
    # JSON
    data = await _load_json_locked()
    block = _ensure_user_block(data, user_id)
    before = len(block["tasks"])
    block["tasks"] = [
        t for t in block["tasks"] if int(t.get("id", -1)) != task_id
    ]
    after = len(block["tasks"])
    await _save_json_locked(data)

    # Postgres
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM task_state
            WHERE user_id = $1 AND task_id = $2
            """,
            user_id,
            task_id,
        )

    return before != after


async def set_due(task_id: int, user_id: int, due_iso: Optional[str]) -> bool:
    """
    Удобный враппер для календаря: due_iso (str|None) -> запись в БД.
    """
    return await update_task(task_id, user_id, due_at=due_iso)


# ---------- Функции для notifier (по необходимости) ----------


async def list_due_tasks(until: dt.datetime) -> List[Dict[str, Any]]:
    """
    Возвращает задачи, у которых due_at <= until (UTC).
    Используется notifier'ом.
    """
    if until.tzinfo is None:
        until = until.replace(tzinfo=dt.timezone.utc)
    else:
        until = until.astimezone(dt.timezone.utc)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, task_id, due_at
            FROM task_state
            WHERE due_at IS NOT NULL
              AND due_at <= $1
            """,
            until,
        )

    if not rows:
        return []

    data = await _load_raw_json()

    result: List[Dict[str, Any]] = []
    for r in rows:
        uid = int(r["user_id"])
        tid = int(r["task_id"])
        due_at = _dt_to_iso(r["due_at"])

        block = data.get(str(uid))
        if not isinstance(block, dict):
            continue
        base = _find_task_in_block(block, tid)
        if not base:
            continue

        result.append(
            {
                "user_id": uid,
                "id": tid,
                "text": str(base.get("text", "")),
                "due_at": due_at,
            }
        )

    return result


async def clear_task_due(user_id: int, task_id: int) -> None:
    """
    Сбрасывает дедлайн (чтобы notifier не дёргал задачу повторно).
    """
    await update_task(task_id, user_id, due_at=None)


# ---------- UI message_id в Postgres ----------


async def get_ui_message_id(chat_id: int, user_id: int) -> Optional[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT message_id
            FROM ui_state
            WHERE chat_id = $1 AND user_id = $2
            """,
            chat_id,
            user_id,
        )
    if row:
        return int(row["message_id"])
    return None


async def set_ui_message_id(chat_id: int, user_id: int, message_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ui_state (user_id, chat_id, message_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, chat_id)
            DO UPDATE SET message_id = EXCLUDED.message_id
            """,
            user_id,
            chat_id,
            message_id,
        )


async def clear_ui_message_id(chat_id: int, user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM ui_state
            WHERE user_id = $1 AND chat_id = $2
            """,
            user_id,
            chat_id,
        )
