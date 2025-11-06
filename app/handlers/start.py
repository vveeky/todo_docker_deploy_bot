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
        await event.answer(START_TEXT, reply_markup=build_start_keyboard())
    else:
        await event.answer()
        try:
            await event.message.edit_text(
                START_TEXT,
                reply_markup=build_start_keyboard(),
            )
        except Exception:
            await event.message.answer(
                START_TEXT,
                reply_markup=build_start_keyboard(),
            )


@start_router.message(Command("help"))
@start_router.callback_query(F.data == "cmd_help")
async def help_cmd(event: Union[Message, CallbackQuery]):
    if isinstance(event, Message):
        await event.answer(HELP_TEXT, reply_markup=build_help_keyboard())
    else:
        await event.answer()
        try:
            await event.message.edit_text(
                HELP_TEXT,
                reply_markup=build_help_keyboard(),
            )
        except Exception:
            await event.message.answer(
                HELP_TEXT,
                reply_markup=build_help_keyboard(),
            )
