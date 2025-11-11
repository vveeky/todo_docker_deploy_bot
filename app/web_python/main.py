# app/web_python/main.py
from pathlib import Path
import datetime as dt

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.utils import storage, dates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TODO Web (Python templates)")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user_id: int, mode: str = "normal"):
    """
    Главная страница.
    user_id берём из query-параметра: /?user_id=123456
    mode = "normal" | "delete" для режима удаления.
    """
    tasks = await storage.list_user_tasks(user_id)
    for t in tasks:
        t["created_at_fmt"] = dates.format_dt(t.get("created_at"))
        t["due_at_fmt"] = dates.format_dt(t.get("due_at"))

    delete_mode = mode == "delete"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tasks": tasks,
            "user_id": user_id,
            "delete_mode": delete_mode,
        },
    )


@app.post("/tasks/add")
async def add_task(
    user_id: int = Form(...),
    text: str = Form(...),
):
    text = text.strip()
    if text:
        await storage.add_task(user_id, text)
    return RedirectResponse(url=f"/?user_id={user_id}", status_code=303)


@app.post("/tasks/{task_id}/toggle")
async def toggle_task(
    task_id: int,
    user_id: int = Form(...),
):
    task = await storage.get_task(task_id, user_id)
    if task is not None:
        new_value = 0 if task.get("is_done") else 1
        await storage.update_task(task_id, user_id, is_done=new_value)
    return RedirectResponse(url=f"/?user_id={user_id}", status_code=303)


@app.post("/tasks/{task_id}/delete")
async def delete_task(
    task_id: int,
    user_id: int = Form(...),
):
    await storage.delete_task(task_id, user_id)
    return RedirectResponse(url=f"/?user_id={user_id}", status_code=303)


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    task_id: int,
    user_id: int,
):
    task = await storage.get_task(task_id, user_id)
    if task is None:
        return RedirectResponse(url=f"/?user_id={user_id}", status_code=303)

    task_view = dict(task)
    task_view["created_at_fmt"] = dates.format_dt(task.get("created_at"))
    task_view["due_at_fmt"] = dates.format_dt(task.get("due_at"))

    due_input = ""
    if task.get("due_at"):
        try:
            dt_obj = dt.datetime.fromisoformat(task["due_at"])
            due_input = dt_obj.strftime("%Y-%m-%d %H:%M")
        except Exception:
            due_input = task["due_at"]

    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "user_id": user_id,
            "task": task_view,
            "due_input": due_input,
        },
    )


@app.post("/tasks/{task_id}/edit")
async def edit_task(
    task_id: int,
    user_id: int = Form(...),
    text: str = Form(...),
    due_at: str = Form(""),
):
    text = (text or "").strip()
    due_raw = (due_at or "").strip()

    task = await storage.get_task(task_id, user_id)
    if task is None:
        return RedirectResponse(url=f"/?user_id={user_id}", status_code=303)

    fields = {}

    if text:
        fields["text"] = text
    else:
        fields["text"] = task.get("text", "")

    if due_raw:
        try:
            dt_obj = dt.datetime.strptime(due_raw, "%Y-%m-%d %H:%M")
            fields["due_at"] = dt_obj.replace(second=0, microsecond=0).isoformat()
        except Exception:
            # если формат неправильный, оставляем старый дедлайн
            fields["due_at"] = task.get("due_at")
    else:
        fields["due_at"] = None

    await storage.update_task(task_id, user_id, **fields)

    return RedirectResponse(
        url=f"/tasks/{task_id}?user_id={user_id}",
        status_code=303,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.web_python.main:app", host="0.0.0.0", port=8001, reload=True)
