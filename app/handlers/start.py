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
        [InlineKeyboardButton(text="/start", callback_data="cmd_start")],
        [InlineKeyboardButton(text="/help", callback_data="cmd_help")],
        [InlineKeyboardButton(text="/add", callback_data="cmd_add")],
        [InlineKeyboardButton(text="/list", callback_data="cmd_list")],
        [InlineKeyboardButton(text="/done", callback_data="cmd_done")],
        [InlineKeyboardButton(text="/due", callback_data="cmd_due")],
        [InlineKeyboardButton(text="/delete", callback_data="cmd_delete")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


START_TEXT = (
    "Привет! Я бот для управления задачами.\n"
    "Отправь /help или нажми кнопку."
)

HELP_TEXT = (
    "Команды:\n"
    "/add <текст> — добавить задачу\n"
    "/list — список задач\n"
    "/done <id> — пометить выполненной\n"
    "/due <id> YYYY-MM-DD HH:MM — установить дедлайн\n"
    "/delete <id> — удалить задачу\n\n"
    "Можно также пользоваться кнопками."
)


@start_router.message(Command("start"))
@start_router.callback_query(F.data == "cmd_start")
async def start_cmd(event: Union[Message, CallbackQuery]):
    if isinstance(event, Message):
        try:
            await event.delete()  # убрать команду из чата
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
    await show_screen(event, HELP_TEXT, reply_markup=build_help_keyboard())
