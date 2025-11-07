# app/handlers/todo.py
from typing import Union, List
import datetime as dt
import calendar

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from app.utils import storage
from app.keyboards.tasks_kb import tasks_page_keyboard, DEFAULT_PER_PAGE
from app.states.todo_states import TodoStates
from app.states.date_picker import DatePickerState
from app.utils.ui import show_screen
from app.utils.dates import format_dt

todo_router = Router()


# ======= ХЕЛПЕРЫ ДЛЯ ВЫБОРА ДАТЫ/ВРЕМЕНИ =======

def _dp_normalize_components(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
) -> tuple[int, int, int, int, int]:
    if year < 1970:
        year = 1970
    if year > 2100:
        year = 2100

    if month < 1:
        month = 1
    if month > 12:
        month = 12

    max_day = calendar.monthrange(year, month)[1]
    if day < 1:
        day = 1
    if day > max_day:
        day = max_day

    if hour < 0:
        hour = 0
    if hour > 23:
        hour = 23

    if minute < 0:
        minute = 0
    if minute > 59:
        minute = 59

    return year, month, day, hour, minute


def _dp_current_dt(data: dict) -> dt.datetime:
    year = int(data.get("dp_year"))
    month = int(data.get("dp_month"))
    day = int(data.get("dp_day"))
    hour = int(data.get("dp_hour"))
    minute = int(data.get("dp_minute"))
    year, month, day, hour, minute = _dp_normalize_components(
        year, month, day, hour, minute
    )
    return dt.datetime(year, month, day, hour, minute)


def _dp_stage_label(stage: str) -> str:
    return {
        "day": "день",
        "month": "месяц",
        "hour": "час",
        "minute": "минуты",
        "year": "год",
    }.get(stage, stage)


def _dp_text(data: dict) -> str:
    dt_val = _dp_current_dt(data)
    stage = data.get("dp_stage", "day")
    return (
        "Выбор даты и времени для дедлайна.\n"
        f"Текущая дата: {dt_val.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Текущий шаг: {_dp_stage_label(stage)}.\n"
        "Используй кнопки ниже для изменения.\n"
        "По умолчанию — следующий день, 00:00, если ты ничего не меняешь."
    )


def _dp_build_kb_for_stage(
    stage: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
) -> InlineKeyboardMarkup:
    year, month, day, hour, minute = _dp_normalize_components(
        year, month, day, hour, minute
    )
    rows: list[list[InlineKeyboardButton]] = []

    if stage == "day":
        max_day = calendar.monthrange(year, month)[1]
        row: list[InlineKeyboardButton] = []
        for d in range(1, max_day + 1):
            text = f"[{d}]" if d == day else str(d)
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"dp:set:day:{d}",
                )
            )
            if len(row) == 7:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        rows.append(
            [
                InlineKeyboardButton(
                    text="Месяц", callback_data="dp:stage:month"
                ),
                InlineKeyboardButton(
                    text="Год", callback_data="dp:stage:year"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Часы", callback_data="dp:stage:hour"
                ),
                InlineKeyboardButton(
                    text="Минуты", callback_data="dp:stage:minute"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Сохранить", callback_data="dp:save"
                ),
            ]
        )

    elif stage == "month":
        month_names = [
            "Янв", "Фев", "Мар", "Апр",
            "Май", "Июн", "Июл", "Авг",
            "Сен", "Окт", "Ноя", "Дек",
        ]
        row: list[InlineKeyboardButton] = []
        for m in range(1, 13):
            label = month_names[m - 1]
            text = f"[{label}]" if m == month else label
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"dp:set:month:{m}",
                )
            )
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        rows.append(
            [
                InlineKeyboardButton(
                    text="День", callback_data="dp:stage:day"
                ),
                InlineKeyboardButton(
                    text="Часы", callback_data="dp:stage:hour"
                ),
                InlineKeyboardButton(
                    text="Минуты", callback_data="dp:stage:minute"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Год", callback_data="dp:stage:year"
                ),
                InlineKeyboardButton(
                    text="✅ Сохранить", callback_data="dp:save"
                ),
            ]
        )

    elif stage == "hour":
        row: list[InlineKeyboardButton] = []
        for h in range(0, 24):
            text = f"[{h}]" if h == hour else str(h)
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"dp:set:hour:{h}",
                )
            )
            if len(row) == 6:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        rows.append(
            [
                InlineKeyboardButton(
                    text="День", callback_data="dp:stage:day"
                ),
                InlineKeyboardButton(
                    text="Месяц", callback_data="dp:stage:month"
                ),
                InlineKeyboardButton(
                    text="Минуты", callback_data="dp:stage:minute"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Год", callback_data="dp:stage:year"
                ),
                InlineKeyboardButton(
                    text="✅ Сохранить", callback_data="dp:save"
                ),
            ]
        )

    elif stage == "minute":
        row: list[InlineKeyboardButton] = []
        for m in range(0, 60, 5):
            text = f"[{m}]" if m == minute else str(m)
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"dp:set:minute:{m}",
                )
            )
            if len(row) == 6:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        rows.append(
            [
                InlineKeyboardButton(
                    text="Часы", callback_data="dp:stage:hour"
                ),
                InlineKeyboardButton(
                    text="День", callback_data="dp:stage:day"
                ),
                InlineKeyboardButton(
                    text="Месяц", callback_data="dp:stage:month"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Год", callback_data="dp:stage:year"
                ),
                InlineKeyboardButton(
                    text="✅ Сохранить", callback_data="dp:save"
                ),
            ]
        )

    else:
        # fallback, не должен использоваться
        rows.append(
            [
                InlineKeyboardButton(
                    text="День", callback_data="dp:stage:day"
                ),
                InlineKeyboardButton(
                    text="Год", callback_data="dp:stage:year"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Сохранить", callback_data="dp:save"
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _dp_build_kb_year() -> InlineKeyboardMarkup:
    """
    Клавиатура для шага 'год' — год вводится текстом,
    кнопки только навигации/сохранения.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ К дню", callback_data="dp:stage:day"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Сохранить", callback_data="dp:save"
                )
            ],
        ]
    )


async def _dp_show_screen(event: Union[Message, CallbackQuery], state: FSMContext) -> None:
    data = await state.get_data()
    stage = data.get("dp_stage", "day")

    year = int(data.get("dp_year"))
    month = int(data.get("dp_month"))
    day = int(data.get("dp_day"))
    hour = int(data.get("dp_hour"))
    minute = int(data.get("dp_minute"))
    year, month, day, hour, minute = _dp_normalize_components(
        year, month, day, hour, minute
    )
    current_dt = dt.datetime(year, month, day, hour, minute)

    if stage == "year":
        text = (
            "Выбор года для дедлайна.\n"
            f"Текущая дата: {current_dt.strftime('%Y-%m-%d %H:%M')}\n\n"
            "Отправь новый год числом, например: 2026.\n"
            "Или нажми «К дню» или «Сохранить»."
        )
        kb = _dp_build_kb_year()
    else:
        text = _dp_text(
            {
                "dp_year": year,
                "dp_month": month,
                "dp_day": day,
                "dp_hour": hour,
                "dp_minute": minute,
                "dp_stage": stage,
            }
        )
        kb = _dp_build_kb_for_stage(stage, year, month, day, hour, minute)

    await show_screen(event, text, reply_markup=kb)


async def _dp_start_for_task(
    event: Union[Message, CallbackQuery],
    state: FSMContext,
    task: dict,
) -> None:
    """
    Запуск пикера дат для конкретной задачи.
    По умолчанию: текущий дедлайн задачи, если есть,
    иначе — следующий день, 00:00.
    """
    if task.get("due_at"):
        try:
            base = dt.datetime.fromisoformat(task["due_at"])
        except Exception:
            base = dt.datetime.now() + dt.timedelta(days=1)
            base = base.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        base = dt.datetime.now() + dt.timedelta(days=1)
        base = base.replace(hour=0, minute=0, second=0, microsecond=0)

    await state.set_state(DatePickerState.picking)
    await state.set_data(
        {
            "dp_mode": "due",
            "dp_task_id": task["id"],
            "dp_stage": "day",
            "dp_year": base.year,
            "dp_month": base.month,
            "dp_day": base.day,
            "dp_hour": base.hour,
            "dp_minute": base.minute,
        }
    )
    await _dp_show_screen(event, state)



async def render_tasks_screen(
    event: Union[Message, CallbackQuery],
    user_id: int,
    page: int = 0,
    prefix: str | None = None,
) -> None:
    tasks = await storage.list_user_tasks(user_id)
    if not tasks:
        text = (prefix + "\n\n" if prefix else "") + "У вас нет задач."
        await show_screen(event, text)
        return

    tasks_sorted = sorted(
        tasks, key=lambda t: (t.get("is_done", 0), t.get("id", 0))
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

    if prefix:
        text = prefix + "\n\n" + header
    else:
        text = header

    kb = tasks_page_keyboard(tasks_sorted, page=page, per_page=DEFAULT_PER_PAGE)
    await show_screen(event, text, reply_markup=kb)


async def render_task_card(
    event: Union[Message, CallbackQuery],
    task: dict,
    prefix: str | None = None,
) -> None:
    tid = task["id"]

    due_str = format_dt(task.get("due_at")) if task.get("due_at") else "—"
    created_str = format_dt(task.get("created_at"))

    text = (
        f"#{task['id']} — {task['text']}\n"
        f"Статус: {'✅' if task.get('is_done') else '✳️'}\n"
        f"Дедлайн: {task.get('due_at') or '—'}\n"
        f"Создано: {task.get('created_at')}"
    )
    if prefix:
        text = prefix + "\n\n" + text

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
            [
                InlineKeyboardButton(
                    text="⬅️ К списку задач",
                    callback_data="cmd_list",
                )
            ],
        ]
    )
    await show_screen(event, text, reply_markup=kb)


# --------- /list + пагинация ---------

@todo_router.message(Command("list"))
@todo_router.callback_query(F.data == "cmd_list")
@todo_router.callback_query(F.data.startswith("tasks:page:"))
async def list_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, Message):
        try:
            await event.delete()
        except Exception:
            pass
        user_id = event.from_user.id
        page = 0
    else:
        user_id = event.from_user.id
        data = event.data or ""
        page = 0
        if data.startswith("tasks:page:"):
            try:
                page = int(data.split(":", 2)[2])
            except ValueError:
                page = 0

    await render_tasks_screen(event, user_id, page=page)


# --------- /add ---------

@todo_router.message(Command("add"))
@todo_router.callback_query(F.data == "cmd_add")
async def add_handler(event: Union[Message, CallbackQuery], state: FSMContext):
    """
    /add или кнопка /add -> переходим в состояние ожидания текста задачи.
    Аргументы после /add игнорируем, всегда ждём новое сообщение с текстом.
    """
    if isinstance(event, Message):
        try:
            await event.delete()  # убираем команду пользователя
        except Exception:
            pass
    else:
        await event.answer()

    await state.set_state(TodoStates.add_text)

    await show_screen(
        event,
        "Создание новой задачи.\n"
        "Отправь текст задачи одним сообщением.",
    )


@todo_router.message(StateFilter(TodoStates.add_text))
async def state_add_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        try:
            await message.delete()
        except Exception:
            pass
        await show_screen(
            message,
            "Текст задачи не может быть пустым.\n"
            "Отправь текст задачи одним сообщением.",
        )
        return

    task = await storage.add_task(message.from_user.id, text)
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    await render_tasks_screen(
        message,
        message.from_user.id,
        page=0,
        prefix=f"Задача добавлена: #{task['id']} — {task['text']}",
    )



# --------- /done ---------

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
        try:
            await event.delete()
        except Exception:
            pass
        await event.bot.send_message(
            chat_id=event.chat.id,
            text="Используй: /done id",
        )
        return

    tid = int(parts[1])
    ok = await storage.mark_done(tid, event.from_user.id)
    try:
        await event.delete()
    except Exception:
        pass

    prefix = (
        f"Задача #{tid} помечена как выполненная."
        if ok
        else "Задача не найдена."
    )
    await render_tasks_screen(event, event.from_user.id, prefix=prefix)


# --------- /due ---------

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
        try:
            await event.delete()
        except Exception:
            pass
        await event.bot.send_message(
            chat_id=event.chat.id,
            text="Используй: /due id YYYY-MM-DD HH:MM",
        )
        return

    try:
        tid = int(parts[1])
    except ValueError:
        try:
            await event.delete()
        except Exception:
            pass
        await event.bot.send_message(
            chat_id=event.chat.id,
            text="Неправильный id.",
        )
        return

    try:
        due_dt = dt.datetime.strptime(parts[2], "%Y-%m-%d %H:%M")
    except Exception:
        try:
            await event.delete()
        except Exception:
            pass
        await event.bot.send_message(
            chat_id=event.chat.id,
            text="Неправильный формат даты. Используй: YYYY-MM-DD HH:MM",
        )
        return

    iso = due_dt.replace(second=0, microsecond=0).isoformat()
    ok = await storage.set_due(tid, event.from_user.id, iso)
    try:
        await event.delete()
    except Exception:
        pass

    prefix = (
        f"Дедлайн для #{tid} установлен: {iso}"
        if ok
        else "Задача не найдена."
    )
    await render_tasks_screen(event, event.from_user.id, prefix=prefix)


# --------- /delete ---------

@todo_router.message(Command("delete"))
@todo_router.callback_query(F.data == "cmd_delete")
async def delete_handler(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer("Чтобы удалить задачу, отправь: /delete ID")
        return

    parts = event.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        try:
            await event.delete()
        except Exception:
            pass
        await event.bot.send_message(
            chat_id=event.chat.id,
            text="Используй: /delete id",
        )
        return

    tid = int(parts[1])
    try:
        await event.delete()
    except Exception:
        pass

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
    await show_screen(
        event,
        f"Подтвердите удаление задачи #{tid}",
        reply_markup=kb,
    )


# --------- карточка задачи ---------

@todo_router.callback_query(F.data.startswith("task:show:"))
async def cb_task_show(query: CallbackQuery):
    await query.answer()
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.message.answer("Некорректный id задачи.")
        return

    task = await storage.get_task(tid, query.from_user.id)
    if not task:
        await query.message.answer("Задача не найдена.")
        return

    await render_task_card(query, task)



# --------- edit text ---------

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

    await show_screen(
        query,
        f"Редактирование текста задачи #{tid}.\n"
        "Отправь новый текст этой задачей отдельным сообщением.",
    )


@todo_router.message(StateFilter(TodoStates.edit_text))
async def state_receive_new_text(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("edit_tid")
    if not tid:
        await state.clear()
        try:
            await message.delete()
        except Exception:
            pass
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="Контекст состояния потерян.",
        )
        return

    new_text = message.text.strip()
    if not new_text:
        try:
            await message.delete()
        except Exception:
            pass
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="Текст не может быть пустым. Отправь новый текст.",
        )
        return

    ok = await storage.update_task(tid, message.from_user.id, text=new_text)
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    if ok:
        prefix = f"Задача #{tid} обновлена."
        task = await storage.get_task(tid, message.from_user.id)
        if task:
            await render_task_card(message, task, prefix=prefix)
            return
    await message.bot.send_message(
        chat_id=message.chat.id,
        text="Задача не найдена или не относится к вам.",
    )



# --------- edit due ---------

@todo_router.callback_query(F.data.startswith("task:edit_due:"))
async def cb_task_edit_due(query: CallbackQuery, state: FSMContext):
    try:
        tid = int(query.data.split(":", 2)[2])
    except Exception:
        await query.answer("Некорректный id задачи.", show_alert=True)
        return

    task = await storage.get_task(tid, query.from_user.id)
    if not task:
        await query.answer("Задача не найдена.", show_alert=True)
        return

    await _dp_start_for_task(query, state, task)



@todo_router.message(StateFilter(TodoStates.edit_due))
async def state_receive_new_due(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("edit_tid")
    if not tid:
        await state.clear()
        try:
            await message.delete()
        except Exception:
            pass
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="Контекст состояния потерян.",
        )
        return

    try:
        due_dt = dt.datetime.strptime(
            message.text.strip(), "%Y-%m-%d %H:%M"
        )
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="Неправильный формат. Используй: YYYY-MM-DD HH:MM",
        )
        return

    iso = due_dt.replace(second=0, microsecond=0).isoformat()
    ok = await storage.set_due(tid, message.from_user.id, iso)
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    if ok:
        prefix = f"Дедлайн для #{tid} установлен: {iso}"
        task = await storage.get_task(tid, message.from_user.id)
        if task:
            await render_task_card(message, task, prefix=prefix)
            return

    await message.bot.send_message(
        chat_id=message.chat.id,
        text="Задача не найдена или не относится к вам.",
    )



# --------- mark done из карточки ---------

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
        task = await storage.get_task(tid, query.from_user.id)
        if task:
            await render_task_card(query, task, prefix=f"Задача #{tid} помечена как выполненная.")
            return

    await query.message.answer("Задача не найдена или не относится к вам.")


# --------- delete из карточки ---------

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
    await show_screen(
        query,
        f"Подтвердите удаление задачи #{tid}",
        reply_markup=kb,
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
    prefix = (
        f"Задача #{tid} удалена."
        if ok
        else "Задача не найдена или не относится к вам."
    )
    await render_tasks_screen(query, query.from_user.id, prefix=prefix)


@todo_router.callback_query(F.data == "task:cancel")
async def cb_cancel(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    await render_tasks_screen(query, query.from_user.id, prefix="Отменено.")


# --------- режим удаления списка ---------

@todo_router.callback_query(F.data == "tasks:delete_mode")
async def cb_tasks_delete_mode(query: CallbackQuery):
    await query.answer()
    tasks = await storage.list_user_tasks(query.from_user.id)
    if not tasks:
        await query.message.answer("У вас нет задач.")
        return

    tasks_sorted = sorted(
        tasks, key=lambda t: (t.get("is_done", 0), t.get("id", 0)),
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
    await show_screen(
        query,
        "Режим удаления: выбери задачу для удаления.",
        reply_markup=kb,
    )


# --------- postpone ---------

@todo_router.callback_query(F.data == "tasks:postpone_prompt")
async def cb_postpone_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TodoStates.postpone_wait_date)
    await show_screen(
        query,
        "Отправь дату и время, до которых отложить все ближайшие "
        "напоминания.\nФормат: YYYY-MM-DD HH:MM (локальное время).",
    )


@todo_router.message(TodoStates.postpone_wait_date)
async def state_receive_postpone_date(message: Message, state: FSMContext):
    try:
        until_dt = dt.datetime.strptime(
            message.text.strip(), "%Y-%m-%d %H:%M"
        )
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="Неправильный формат. Используй YYYY-MM-DD HH:MM",
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
    try:
        await message.delete()
    except Exception:
        pass

    await render_tasks_screen(
        message,
        message.from_user.id,
        prefix=f"Отложено {count} напоминаний до {until_iso}.",
    )


# --------- noop ---------

@todo_router.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery):
    await query.answer()


# --------- catch-all: удалять любой текст ---------

@todo_router.message()
async def trash_any_text(message: Message):
    try:
        await message.delete()
    except Exception:
        pass

# ------- CALENDAR ---------

@todo_router.callback_query(
    StateFilter(DatePickerState.picking),
    F.data.startswith("dp:")
)
async def dp_callback(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parts = query.data.split(":")

    if len(parts) < 2:
        await query.answer()
        return

    kind = parts[1]

    # выбор значения: день/месяц/час/минуты
    if kind == "set" and len(parts) == 4:
        field = parts[2]
        try:
            value = int(parts[3])
        except ValueError:
            await query.answer("Некорректное значение.", show_alert=True)
            return

        if field == "day":
            data["dp_day"] = value
        elif field == "month":
            data["dp_month"] = value
        elif field == "hour":
            data["dp_hour"] = value
        elif field == "minute":
            data["dp_minute"] = value

        await state.set_data(data)
        await _dp_show_screen(query, state)
        return

    # смена шага: day/month/hour/minute/year
    if kind == "stage" and len(parts) == 3:
        target = parts[2]
        if target not in {"day", "month", "hour", "minute", "year"}:
            await query.answer()
            return
        data["dp_stage"] = target
        await state.set_data(data)
        await _dp_show_screen(query, state)
        return

    # сохранение
    if kind == "save":
        mode = data.get("dp_mode")
        if mode != "due":
            await state.clear()
            await show_screen(query, "Контекст выбора даты потерян.")
            return

        try:
            current_dt = _dp_current_dt(data)
        except Exception:
            await query.answer("Не удалось собрать дату.", show_alert=True)
            return

        task_id = data.get("dp_task_id")
        if not isinstance(task_id, int):
            await state.clear()
            await show_screen(query, "Контекст задачи потерян.")
            return

        iso = current_dt.replace(second=0, microsecond=0).isoformat()
        ok = await storage.set_due(task_id, query.from_user.id, iso)
        await state.clear()

        if ok:
            task = await storage.get_task(task_id, query.from_user.id)
            if task:
                prefix = f"Дедлайн установлен: {format_dt(task.get('due_at'))}"
                await render_task_card(query, task, prefix=prefix)
                return
            await show_screen(query, "Дедлайн сохранён, но задача не найдена.")
        else:
            await show_screen(query, "Не удалось сохранить дедлайн.")

        return

    await query.answer()

@todo_router.message(StateFilter(DatePickerState.picking))
async def dp_year_input(message: Message, state: FSMContext):
    data = await state.get_data()
    stage = data.get("dp_stage")

    # Разрешаем текст только на шаге 'year'
    if stage != "year":
        # Любые чужие сообщения в этом состоянии просто удаляем
        try:
            await message.delete()
        except Exception:
            pass
        return

    text = (message.text or "").strip()
    try:
        year = int(text)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        await show_screen(
            message,
            "Год должен быть числом, например: 2025.\n"
            "Попробуй ещё раз, либо нажми «К дню» или «Сохранить».",
        )
        return

    if year < 1970 or year > 2100:
        try:
            await message.delete()
        except Exception:
            pass
        await show_screen(
            message,
            "Год должен быть в диапазоне 1970–2100.\n"
            "Попробуй ещё раз.",
        )
        return

    data["dp_year"] = year
    # после ввода года логично вернуться к дням
    data["dp_stage"] = "day"
    await state.set_data(data)

    try:
        await message.delete()
    except Exception:
        pass

    await _dp_show_screen(message, state)
