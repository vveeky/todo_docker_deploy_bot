# app/handlers/start.py
from typing import Union
import os
import datetime as dt

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.utils.ui import show_screen
from app.states.time_settings import TimeSettingsStates
from app.db.core import (
    get_user_tz_offset,
    set_user_tz_offset,
    get_or_create_web_token,
    rotate_web_token,
)

start_router = Router()

# Базовый URL веб-сайта:
# локально по умолчанию http://127.0.0.1:8001
# на сервере можно переопределить через .env / переменную окружения PYTHON_BASE
PYTHON_BASE = os.getenv("PYTHON_BASE", "http://127.0.0.1:8001")


# ===== ТЕКСТЫ =====

START_TEXT = (
    "Привет! Я бот для управления задачами.\n\n"
    "Жми «/help — список команд» или используй кнопки ниже."
)

HELP_TEXT = (
    "Это TODO-бот.\n\n"
    "Основные действия:\n"
    "• ➕ Добавить задачу\n"
    "• 📋 Показать список задач\n"
    "• 🌐 Открыть веб-интерфейс\n"
    "• 🕒 Настроить время\n\n"
    "Используй кнопки ниже."
)


# ===== КЛАВИАТУРЫ =====

def build_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="список команд",
                    callback_data="cmd_help",
                )
            ]
        ]
    )


def build_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить задачу",
                    callback_data="cmd_add",
                ),
                InlineKeyboardButton(
                    text="📋 Список задач",
                    callback_data="cmd_list",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Открыть сайт",
                    callback_data="cmd_site",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🕒 Настроить время",
                    callback_data="cmd_time",
                ),
            ],
        ]
    )


def build_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отменить",
                    callback_data="cmd_time_cancel",
                )
            ]
        ]
    )



def build_site_keyboard(token: str) -> InlineKeyboardMarkup:
    python_url = f"{PYTHON_BASE}/?token={token}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть сайт 🌐",
                    web_app=WebAppInfo(url=python_url),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♻️ Сбросить веб-токен",
                    callback_data="web:reset_token",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к командам",
                    callback_data="cmd_help",
                ),
            ],
        ]
    )



# ===== /start (+ callback cmd_start) =====

@start_router.message(Command("start"))
@start_router.callback_query(F.data == "cmd_start")
async def start_cmd(
    event: Union[Message, CallbackQuery],
    state: FSMContext,
):
    # 1. user_id из Message или CallbackQuery
    if isinstance(event, CallbackQuery):
        await event.answer()
        user_id = event.from_user.id
    else:
        user_id = event.from_user.id

    # 2. проверяем, настроен ли часовой пояс
    offset = await get_user_tz_offset(user_id)
    if offset is None:
        now = dt.datetime.now()
        server_time_str = now.strftime("%H:%M")

        await state.set_state(TimeSettingsStates.waiting_for_time)

        text = (
            "Перед началом работы нужно настроить время.\n\n"
            f"Сейчас на сервере: {server_time_str}.\n\n"
            "Напиши, сколько у тебя сейчас времени, в формате HH:MM.\n"
            "Минуты должны совпадать с минутами, показанными выше."
        )

        msg = event.message if isinstance(event, CallbackQuery) else event
        await msg.answer(text)

        return

    # 3. обычный стартовый экран
    if isinstance(event, Message):
        try:
            await event.delete()  # убрать /start из чата
        except Exception:
            pass

    await show_screen(event, START_TEXT, reply_markup=build_start_keyboard())




# ===== /help (+ callback cmd_help) =====

@start_router.message(Command("help"))
@start_router.callback_query(F.data == "cmd_help")
async def help_cmd(event: Union[Message, CallbackQuery]):
    if isinstance(event, Message):
        try:
            await event.delete()
        except Exception:
            pass
    else:
        try:
            await event.answer()
        except Exception:
            pass

    await show_screen(event, HELP_TEXT, reply_markup=build_help_keyboard())


# ===== /site (+ callback cmd_site) =====

@start_router.message(Command("site"))
@start_router.callback_query(F.data == "cmd_site")
async def cmd_site(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()
        user_id = event.from_user.id
    else:
        user_id = event.from_user.id
        try:
            await event.delete()
        except Exception:
            pass

    token = await get_or_create_web_token(user_id)
    kb = build_site_keyboard(token)

    await show_screen(
        event,
        "Веб-интерфейс задач. Нажми кнопку ниже, чтобы открыть сайт.",
        reply_markup=kb,
    )


@start_router.callback_query(F.data == "web:reset_token")
async def cb_web_reset_token(query: CallbackQuery):
    await query.answer()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, сбросить",
                    callback_data="web:reset_token:confirm",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="cmd_site",
                ),
            ],
        ]
    )

    await show_screen(
        query,
        (
            "Точно сбросить веб-токен?\n"
            "Старые ссылки перестанут работать, "
            "нужно будет открыть сайт по новой ссылке."
        ),
        reply_markup=kb,
    )


@start_router.callback_query(F.data == "web:reset_token:confirm")
async def cb_web_reset_token_confirm(query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id

    new_token = await rotate_web_token(user_id)
    kb = build_site_keyboard(new_token)

    await show_screen(
        query,
        "Готово. Веб-токен сброшен. Используй новую ссылку ниже.",
        reply_markup=kb,
    )



# ===== /time (+ callback cmd_time) — переустановка часового пояса =====

@start_router.message(Command("time"))
@start_router.callback_query(F.data == "cmd_time")
async def cmd_time(event: Union[Message, CallbackQuery], state: FSMContext):
    if isinstance(event, CallbackQuery):
        await event.answer()

    now = dt.datetime.now()
    server_time_str = now.strftime("%H:%M")

    await state.set_state(TimeSettingsStates.waiting_for_time)
    await show_screen(
        event,
        (
            "Перенастроим время.\n\n"
            f"Сейчас на сервере: {server_time_str}.\n\n"
            "Напиши, сколько у тебя сейчас времени, в формате HH:MM.\n"
            "Минуты должны совпадать."
        ),
        reply_markup=build_time_keyboard(),
    )


@start_router.callback_query(F.data == "cmd_time_cancel")
async def cmd_time_cancel(event: CallbackQuery, state: FSMContext):
    await event.answer()
    await state.clear()
    await show_screen(
        event,
        START_TEXT,
        reply_markup=build_start_keyboard(),
    )



# ===== обработка ввода времени в формате HH:MM =====

@start_router.message(TimeSettingsStates.waiting_for_time)
async def tz_handle_time_input(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass

    # парсим HH:MM
    try:
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError
        user_h = int(parts[0])
        user_m = int(parts[1])
        if not (0 <= user_h <= 23 and 0 <= user_m <= 59):
            raise ValueError
    except ValueError:
        await show_screen(
            message,
            "Введи время в формате HH:MM, например 09:30.",
        )
        return

    # текущее время на сервере
    now = dt.datetime.now()
    server_h = now.hour
    server_m = now.minute

    # минуты должны совпадать
    if user_m != server_m:
        server_time_str = now.strftime("%H:%M")
        await show_screen(
            message,
            (
                "Минуты должны совпадать с серверными.\n"
                f"Сейчас на сервере: {server_time_str}.\n"
                "Введи своё время так, чтобы минуты были такими же."
            ),
        )
        return

    # считаем разницу (server - user) в минутах, с учётом перехода через полночь
    server_total = server_h * 60 + server_m
    user_total = user_h * 60 + user_m
    diff = server_total - user_total  # server - user

    # нормализуем в диапазон [-12ч, +12ч], чтобы не было странных смещений
    if diff > 12 * 60:
        diff -= 24 * 60
    elif diff < -12 * 60:
        diff += 24 * 60

    offset_minutes = diff  # tz_offset_minutes

    await set_user_tz_offset(message.from_user.id, offset_minutes)
    await state.clear()

    await show_screen(
        message,
        (
            "Часовой пояс настроен.\n"
            f"Смещение относительно сервера: {offset_minutes:+d} минут.\n"
            "Теперь дедлайны будут считаться относительно твоего времени."
        ),
        reply_markup=build_start_keyboard(),
    )
