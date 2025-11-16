# app/web_python/main.py
from pathlib import Path
import datetime as dt

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.db.core import init_db_and_schema, get_user_id_by_token, get_user_tz_offset
from app.utils import storage


# === Загрузка .env ===

# ищем .env в корне проекта (на 2 уровня вверх от этого файла: app/web_python -> app -> проект)
project_root = Path(__file__).resolve().parents[2]
dotenv_path = project_root / ".env"

# если .env существует — явно подгружаем его, иначе пробуем дефолтное поведение
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    load_dotenv()


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TODO Web (Python templates)")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# === Хелперы для времени ===

def _to_local_str(dt_value, offset_minutes: int) -> str:
    """
    Переводит UTC-дату/дату без tz в строку ЛОКАЛЬНОГО времени пользователя.

    tz_offset_minutes хранится как (server - user), поэтому:
        local = utc - offset
    """
    if not dt_value:
        return "—"

    # на вход может прийти str или datetime
    if isinstance(dt_value, str):
        try:
            d = dt.datetime.fromisoformat(dt_value)
        except Exception:
            return dt_value
    else:
        d = dt_value

    # приводим к UTC-naive
    if d.tzinfo is None:
        d_utc = d
    else:
        d_utc = d.astimezone(dt.timezone.utc).replace(tzinfo=None)

    local = d_utc - dt.timedelta(minutes=int(offset_minutes or 0))
    return local.replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")


def _local_str_to_utc_iso(due_raw: str, offset_minutes: int) -> str | None:
    """
    Строка 'YYYY-MM-DD HH:MM' в ЛОКАЛЬНОМ времени пользователя -> ISO в UTC.

    tz_offset_minutes хранится как (server - user), поэтому:
        utc = local + offset
    """
    if not due_raw:
        return None
    try:
        local = dt.datetime.strptime(due_raw, "%Y-%m-%d %H:%M")
    except Exception:
        return None

    utc_naive = local + dt.timedelta(minutes=int(offset_minutes or 0))
    return utc_naive.replace(
        tzinfo=dt.timezone.utc,
        second=0,
        microsecond=0,
    ).isoformat()


# === Старт/шаблоны ===

@app.on_event("startup")
async def on_startup():
    await init_db_and_schema()


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# === Роуты ===

@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    token: str = Query(""),
    mode: str = "normal",
):
    """
    Главная страница.
    Доступ по токену: /?token=...
    mode = "normal" | "delete" для режима удаления.
    """
    user_id = await _resolve_user_id_or_403(token)
    offset = await get_user_tz_offset(user_id)
    offset = int(offset or 0)

    tasks = await storage.list_user_tasks(user_id)
    tasks_view = []
    for t in tasks:
        tasks_view.append(
            {
                **t,
                "created_at_fmt": _to_local_str(t.get("created_at"), offset),
                "due_at_fmt": _to_local_str(t.get("due_at"), offset),
            }
        )

    delete_mode = mode == "delete"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tasks": tasks_view,
            "user_id": user_id,
            "token": token,
            "delete_mode": delete_mode,
        },
    )


@app.post("/tasks/add")
async def add_task(
    token: str = Form(...),
    text: str = Form(...),
):
    user_id = await _resolve_user_id_or_403(token)

    text = text.strip()
    if text:
        await storage.add_task(user_id, text)
    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.post("/tasks/{task_id}/toggle")
async def toggle_task(
    task_id: int,
    token: str = Form(...),
):
    user_id = await _resolve_user_id_or_403(token)

    task = await storage.get_task(task_id, user_id)
    if task is not None:
        new_value = 0 if task.get("is_done") else 1
        await storage.update_task(task_id, user_id, is_done=new_value)
    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.post("/tasks/{task_id}/delete")
async def delete_task(
    task_id: int,
    token: str = Form(...),
):
    user_id = await _resolve_user_id_or_403(token)

    await storage.delete_task(task_id, user_id)
    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    task_id: int,
    token: str = Query(""),
):
    user_id = await _resolve_user_id_or_403(token)

    offset = await get_user_tz_offset(user_id)
    offset = int(offset or 0)

    task = await storage.get_task(task_id, user_id)
    if task is None:
        return RedirectResponse(url=f"/?token={token}", status_code=303)

    # считаем "человеческий" номер задачи (позиция в списке)
    tasks_all = await storage.list_user_tasks(user_id)
    tasks_sorted = sorted(
        tasks_all,
        key=lambda t: (t.get("is_done", 0), t.get("id", 0)),
    )
    display_num = task_id
    for idx, t in enumerate(tasks_sorted, start=1):
        if int(t.get("id", -1)) == task_id:
            display_num = idx
            break
    
    task_view = {
        **task,
        "display_num": display_num,
        "created_at_fmt": _to_local_str(task.get("created_at"), offset),
        "due_at_fmt": _to_local_str(task.get("due_at"), offset),
    }

    # поле ввода дедлайна — в ЛОКАЛЬНОМ времени пользователя
    due_input = ""
    if task.get("due_at"):
        due_input = _to_local_str(task.get("due_at"), offset)
        # input ожидает формат 'YYYY-MM-DD HH:MM'
        if len(due_input) >= 16:
            due_input = due_input[:16]

    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "user_id": user_id,
            "token": token,
            "task": task_view,
            "due_input": due_input,
        },
    )


@app.post("/tasks/{task_id}/edit")
async def edit_task(
    task_id: int,
    token: str = Form(...),
    text: str = Form(...),
    due_at: str = Form(""),
):
    user_id = await _resolve_user_id_or_403(token)

    text = (text or "").strip()
    due_raw = (due_at or "").strip()

    task = await storage.get_task(task_id, user_id)
    if task is None:
        return RedirectResponse(url=f"/?token={token}", status_code=303)

    fields: dict = {}

    if text:
        fields["text"] = text
    else:
        fields["text"] = task.get("text", "")

    offset = await get_user_tz_offset(user_id)
    offset = int(offset or 0)

    if due_raw:
        # пользователь ввёл ЛОКАЛЬНОЕ время → переводим в UTC перед сохранением
        due_iso = _local_str_to_utc_iso(due_raw, offset)
        if due_iso is not None:
            fields["due_at"] = due_iso
        else:
            # если формат неправильный, оставляем старый дедлайн
            fields["due_at"] = task.get("due_at")
    else:
        fields["due_at"] = None

    await storage.update_task(task_id, user_id, **fields)

    return RedirectResponse(
        url=f"/tasks/{task_id}?token={token}",
        status_code=303,
    )


# === Вспомогательное ===

async def _resolve_user_id_or_403(token: str) -> int:
    user_id = await get_user_id_by_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired web token",
        )
    return user_id


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.web_python.main:app", host="0.0.0.0", port=8001, reload=True)
