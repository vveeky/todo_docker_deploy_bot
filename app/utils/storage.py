# app/utils/storage.py
import os
import json
import asyncio
import datetime as dt
from typing import List, Dict, Any, Optional

import aiofiles

DATA_PATH = os.getenv("DATA_PATH", "data/tasks.json")
_lock = asyncio.Lock()


async def _ensure_file() -> None:
    directory = os.path.dirname(DATA_PATH)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    if not os.path.exists(DATA_PATH):
        async with aiofiles.open(DATA_PATH, "w") as f:
            await f.write(json.dumps({"tasks": []}, ensure_ascii=False))


async def _load_state_unlocked() -> Dict[str, Any]:
    await _ensure_file()
    async with aiofiles.open(DATA_PATH, "r") as f:
        text = await f.read()
    if not text.strip():
        return {"tasks": []}
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return {"tasks": []}
        if "tasks" not in data or not isinstance(data["tasks"], list):
            data["tasks"] = []
        return data
    except Exception:
        return {"tasks": []}


async def _save_state_unlocked(state: Dict[str, Any]) -> None:
    await _ensure_file()
    async with aiofiles.open(DATA_PATH, "w") as f:
        await f.write(json.dumps(state, ensure_ascii=False))


async def load_state() -> Dict[str, Any]:
    async with _lock:
        return await _load_state_unlocked()


async def save_state(state: Dict[str, Any]) -> None:
    async with _lock:
        await _save_state_unlocked(state)


def _next_id(tasks: List[Dict[str, Any]]) -> int:
    ids = [t.get("id", 0) for t in tasks if isinstance(t.get("id"), int)]
    return (max(ids) + 1) if ids else 1


def _utcnow_iso() -> str:
    import datetime as dt
    return dt.datetime.now().replace(microsecond=0).isoformat()


async def list_tasks() -> List[Dict[str, Any]]:
    state = await load_state()
    return state.get("tasks", [])


async def list_user_tasks(user_id: int) -> List[Dict[str, Any]]:
    tasks = await list_tasks()
    return [t for t in tasks if t.get("user_id") == user_id]


async def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    tasks = await list_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            return t
    return None


async def add_task(user_id: int, text: str) -> Dict[str, Any]:
    async with _lock:
        state = await _load_state_unlocked()
        tasks = state.setdefault("tasks", [])
        tid = _next_id(tasks)
        task = {
            "id": tid,
            "user_id": user_id,
            "text": text,
            "is_done": 0,
            "due_at": None,
            "created_at": _utcnow_iso(),
        }
        tasks.append(task)
        await _save_state_unlocked(state)
        return task


async def update_task(task_id: int, user_id: int, **fields: Any) -> bool:
    allowed = {"text", "is_done", "due_at"}
    async with _lock:
        state = await _load_state_unlocked()
        tasks = state.setdefault("tasks", [])
        updated = False
        for t in tasks:
            if t.get("id") == task_id and t.get("user_id") == user_id:
                for key, value in fields.items():
                    if key in allowed:
                        t[key] = value
                updated = True
                break
        if updated:
            await _save_state_unlocked(state)
        return updated


async def mark_done(task_id: int, user_id: int) -> bool:
    return await update_task(task_id, user_id, is_done=1)


async def set_due(task_id: int, user_id: int, due_iso: str) -> bool:
    return await update_task(task_id, user_id, due_at=due_iso)


async def delete_task(task_id: int, user_id: int) -> bool:
    async with _lock:
        state = await _load_state_unlocked()
        tasks = state.setdefault("tasks", [])
        for idx, t in enumerate(tasks):
            if t.get("id") == task_id and t.get("user_id") == user_id:
                tasks.pop(idx)
                await _save_state_unlocked(state)
                return True
        return False
