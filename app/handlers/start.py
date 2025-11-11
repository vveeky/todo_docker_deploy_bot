# app/handlers/start.py
from typing import Union

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command

from app.utils.ui import show_screen

start_router = Router()

PYTHON_BASE = "http://127.0.0.1:8001"


def build_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="/help — список команд",
                    callback_data="cmd_help",
                )
            ]
        ]
    )


def build_help_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="добавить задачу", callback_data="cmd_add")],
        [InlineKeyboardButton(text="список задач", callback_data="cmd_list")],
        [InlineKeyboardButton(text="сайт (Python web)", callback_data="cmd_site")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


START_TEXT = (
    "Привет! Я бот для управления задачами.\n"
    "Отправь /help или нажми кнопку."
)

HELP_TEXT = (
    "Команды:"
)


@start_router.message(Command("start"))
@start_router.callback_query(F.data == "cmd_start")
async def start_cmd(event: Union[Message, CallbackQuery]):
    if isinstance(event, Message):
        try:
            await event.delete()  # убрать команду из чата
        except Exception:
            pass
    else:
        try:
            await event.answer()
        except Exception:
            pass
    await show_screen(event, START_TEXT, reply_markup=build_start_keyboard())


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


@start_router.message(Command("site"))
@start_router.callback_query(F.data == "cmd_site")
async def cmd_site(message: Message):
    uid = message.from_user.id

    python_url = f"{PYTHON_BASE}/?user_id={uid}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Python web", url=python_url),
                InlineKeyboardButton(text="Назад к боту", callback_data="cmd_help"),
            ]
        ]
    )

    try:
            await message.delete()
    except Exception:
            pass

    await show_screen(
            message,
            "Открой веб (только если запущен локально по 8001 порту):",
            reply_markup=kb,
        )
