# app/handlers/todo.py
from typing import Union, List
import datetime as dt

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.utils import storage
from app.keyboards.tasks_kb import tasks_page_keyboard, DEFAULT_PER_PAGE
from app.states.todo_states import TodoStates

todo_router = Router()


async def send_tasks_list(target_message: Message, user_id: int, page: int = 0):
    tasks = await storage.list_user_tasks(user_id)
    if not tasks:
        await target_message.answer("У вас нет задач.")
        return

    tasks_sorted = sorted(
        tasks,
        key=lambda t: (t.get("is_done", 0), t.get("id", 0)),
    )
    total = len(tasks_sorted)
    total_pages = (total + DEFAULT_PER_PAGE - 1) // DEFAULT_PER_PAGE
    if page < 0:
        page = 0
    if page > total_pages - 1:
        page = total_pages - 1

    start = page * DEFAULT_PER_PAGE + 1
    end = min((page + 1) * DEFAULT_PER_PAGE, total)
    header = f"Задачи {start}-{end} из {total}:"

    kb = tasks_page_keyboard(tasks_sorted, page=page, per_page=DEFAULT_PER_PAGE)
    await target_message.answer(header, reply_markup=kb)


@todo_router.message(Command("list"))
@todo_router.callback_query(F.data == "cmd_list")
@todo_router.callback_query(F.data.startswith("tasks:page:"))
async def list_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, Message):
        user_id = event.from_user.id
        page = 0
        target = event
    else:
        await event.answer()
        user_id = event.from_user.id
        data = event.data or ""
        page = 0
        if data.startswith("tasks:page:"):
            try:
                page = int(data.split(":", 2)[2])
            except ValueError:
                page = 0
        target = event.message

    await send_tasks_list(target, user_id, page=page)


@todo_router.message(Command("add"))
@todo_router.callback_query(F.data == "cmd_add")
async def add_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(
            "Чтобы добавить задачу, отправь: /add ТЕКСТ_ЗАДАЧИ"
        )
        return

    text = event.text.partition(" ")[2].strip()
    if not text:
        await event.answer("Используй: /add текст_задачи")
        return

    task = await storage.add_task(event.from_user.id, text)
    await event.answer(f"Добавлено: #{task['id']} — {task['text']}")


@todo_router.message(Command("done"))
@todo_router.callback_query(F.data == "cmd_done")
async def done_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(
            "Чтобы пометить задачу выполненной, отправь: /done ID"
        )
        return

    parts = event.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await event.answer("Используй: /done id")
        return

    tid = int(parts[1])
    ok = await storage.mark_done(tid, event.from_user.id)
    if ok:
        await event.answer(f"Задача #{tid} помечена как выполненная.")
    else:
        await event.answer("Задача не найдена.")


@todo_router.message(Command("due"))
@todo_router.callback_query(F.data == "cmd_due")
async def due_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(
            "Чтобы установить дедлайн, отправь: /due ID YYYY-MM-DD HH:MM"
        )
        return

    parts = event.text.split(maxsplit=2)
    if len(parts) < 3:
        await event.answer("Используй: /due id YYYY-MM-DD HH:MM")
        return

    try:
        tid = int(parts[1])
    except ValueError:
        await event.answer("Неправильный id.")
        return

    try:
        due_dt = dt.datetime.strptime(parts[2], "%Y-%m-%d %H:%M")
    except Exception:
        await event.answer(
            "Неправильный формат даты. Используй: YYYY-MM-DD HH:MM"
        )
        return

    iso = due_dt.replace(second=0, microsecond=0).isoformat()
    ok = await storage.set_due(tid, event.from_user.id, iso)
    if ok:
        await event.answer(f"Дедлайн для #{tid} установлен: {iso}")
    else:
        await event.answer("Задача не найдена.")


@todo_router.message(Command("delete"))
@todo_router.callback_query(F.data == "cmd_delete")
async def delete_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer("Чтобы удалить задачу, отправь: /delete ID")
        return

    parts = event.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await event.answer("Используй: /delete id")
        return

    tid = int(parts[1])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Удалить ❌",
                    callback_data=f"task:do_delete:{tid}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="task:cancel",
                ),
            ]
        ]
    )
    await event.answer(
        f"Подтвердите удаление задачи #{tid}", reply_markup=kb
    )


@todo_router.callback_query(F.data.startswith("task:show:"))
async def cb_task_show(query: CallbackQuery):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    task = await storage.get_task(tid)
    if not task or task.get("user_id") != query.from_user.id:
        await query.message.answer("Задача не найдена.")
        return

    text = (
        f"#{task['id']} — {task['text']}\n"
        f"Статус: {'✅' if task.get('is_done') else '✳️'}\n"
        f"Дедлайн: {task.get('due_at') or '—'}\n"
        f"Создано: {task.get('created_at')}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Изменить текст",
                    callback_data=f"task:edit_text:{tid}",
                ),
                InlineKeyboardButton(
                    text="Изменить дедлайн",
                    callback_data=f"task:edit_due:{tid}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Пометить как выполнено",
                    callback_data=f"task:mark_done:{tid}",
                ),
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"task:confirm_delete:{tid}",
                ),
            ],
        ]
    )
    await query.message.answer(text, reply_markup=kb)


@todo_router.callback_query(F.data.startswith("task:edit_text:"))
async def cb_task_edit_text(query: CallbackQuery, state: FSMContext):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    await state.set_state(TodoStates.edit_text)
    await state.update_data(edit_tid=tid)
    await query.message.answer("Отправь новый текст задачи:")


@todo_router.message(TodoStates.edit_text)
async def state_receive_new_text(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("edit_tid")
    if not tid:
        await message.answer("Контекст состояния потерян.")
        await state.clear()
        return

    new_text = message.text.strip()
    if not new_text:
        await message.answer(
            "Текст не может быть пустым. Отправь новый текст или /cancel."
        )
        return

    ok = await storage.update_task(tid, message.from_user.id, text=new_text)
    await state.clear()
    if ok:
        await message.answer(f"Задача #{tid} обновлена.")
    else:
        await message.answer("Задача не найдена или не относится к вам.")


@todo_router.callback_query(F.data.startswith("task:edit_due:"))
async def cb_task_edit_due(query: CallbackQuery, state: FSMContext):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    await state.set_state(TodoStates.edit_due)
    await state.update_data(edit_tid=tid)
    await query.message.answer(
        "Отправь новый дедлайн в формате: YYYY-MM-DD HH:MM (UTC)"
    )


@todo_router.message(TodoStates.edit_due)
async def state_receive_new_due(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("edit_tid")
    if not tid:
        await message.answer("Контекст состояния потерян.")
        await state.clear()
        return

    try:
        due_dt = dt.datetime.strptime(
            message.text.strip(), "%Y-%m-%d %H:%M"
        )
    except Exception:
        await message.answer(
            "Неправильный формат. Используй: YYYY-MM-DD HH:MM"
        )
        return

    iso = due_dt.replace(second=0, microsecond=0).isoformat()
    ok = await storage.set_due(tid, message.from_user.id, iso)
    await state.clear()
    if ok:
        await message.answer(f"Дедлайн для #{tid} установлен: {iso}")
    else:
        await message.answer("Задача не найдена или не относится к вам.")


@todo_router.callback_query(F.data.startswith("task:mark_done:"))
async def cb_task_mark_done(query: CallbackQuery):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    ok = await storage.mark_done(tid, query.from_user.id)
    if ok:
        await query.message.answer(f"Задача #{tid} помечена как выполненная.")
    else:
        await query.message.answer("Задача не найдена или не относится к вам.")


@todo_router.callback_query(F.data.startswith("task:confirm_delete:"))
async def cb_task_confirm_delete(query: CallbackQuery):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Удалить ❌",
                    callback_data=f"task:do_delete:{tid}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="task:cancel",
                ),
            ]
        ]
    )
    await query.message.answer(
        f"Подтвердите удаление задачи #{tid}", reply_markup=kb
    )


@todo_router.callback_query(F.data.startswith("task:do_delete:"))
async def cb_task_do_delete(query: CallbackQuery):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    ok = await storage.delete_task(tid, query.from_user.id)
    if ok:
        await query.message.answer(f"Задача #{tid} удалена.")
    else:
        await query.message.answer("Задача не найдена или не относится к вам.")


@todo_router.callback_query(F.data == "task:cancel")
async def cb_cancel(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    await query.message.answer("Отменено.")


@todo_router.callback_query(F.data == "tasks:delete_mode")
async def cb_tasks_delete_mode(query: CallbackQuery):
    await query.answer()
    tasks = await storage.list_user_tasks(query.from_user.id)
    if not tasks:
        await query.message.answer("У вас нет задач.")
        return

    tasks_sorted = sorted(
        tasks,
        key=lambda t: (t.get("is_done", 0), t.get("id", 0)),
    )
    rows: List[List[InlineKeyboardButton]] = []
    for t in tasks_sorted:
        tid = t.get("id")
        text = t.get("text", "")
        label = f"{tid}. {text[:40]}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"task:confirm_delete:{tid}",
                )
            ]
        )

    rows.append(
        [InlineKeyboardButton(text="Назад к списку", callback_data="cmd_list")]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await query.message.answer(
        "Режим удаления: выбери задачу для удаления.",
        reply_markup=kb,
    )


@todo_router.callback_query(F.data == "tasks:postpone_prompt")
async def cb_postpone_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TodoStates.postpone_wait_date)
    await query.message.answer(
        "Отправь дату и время, до которого отложить все ближайшие "
        "напоминания.\nФормат: YYYY-MM-DD HH:MM (UTC)."
    )


@todo_router.message(TodoStates.postpone_wait_date)
async def state_receive_postpone_date(message: Message, state: FSMContext):
    try:
        until_dt = dt.datetime.strptime(
            message.text.strip(), "%Y-%m-%d %H:%M"
        )
    except Exception:
        await message.answer(
            "Неправильный формат. Используй YYYY-MM-DD HH:MM"
        )
        return

    until_iso = until_dt.replace(second=0, microsecond=0).isoformat()
    tasks = await storage.list_user_tasks(message.from_user.id)
    count = 0
    for t in tasks:
        due_at = t.get("due_at")
        if not due_at:
            continue
        try:
            current_due = dt.datetime.fromisoformat(due_at)
        except Exception:
            continue
        if current_due < until_dt:
            await storage.set_due(t["id"], message.from_user.id, until_iso)
            count += 1

    await state.clear()
    await message.answer(f"Отложено {count} напоминаний до {until_iso}.")


@todo_router.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery):
    await query.answer()
