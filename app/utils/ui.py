# app/utils/ui.py
from typing import Optional, Union

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from app.utils import storage


async def _resolve_chat_user(
    event: Union[Message, CallbackQuery],
) -> tuple[Bot, int, int]:
    if isinstance(event, CallbackQuery):
        bot: Bot = event.bot
        user_id = event.from_user.id
        chat_id = event.message.chat.id
    else:
        bot = event.bot
        user_id = event.from_user.id
        chat_id = event.chat.id
    return bot, chat_id, user_id


async def show_screen(
    event: Union[Message, CallbackQuery],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """
    Единый UI-экран:
    - message_id хранится в Postgres (ui_state);
    - пытаемся редактировать, если не вышло — удаляем и создаём новый;
    - новый message_id пишем в ui_state.
    """
    bot, chat_id, user_id = await _resolve_chat_user(event)
    msg_id = await storage.get_ui_message_id(chat_id, user_id)

    if msg_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest:
            # пробуем удалить и потом создать новое
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except TelegramBadRequest:
                pass
            except Exception:
                pass
        except Exception:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass

    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    await storage.set_ui_message_id(chat_id, user_id, sent.message_id)


async def show_notification(
    bot: Bot,
    chat_id: int,
    user_id: int,
    text: str,
) -> None:
    """
    Уведомление для notifier:
    - пытается перезаписать текущий UI-экран;
    - если не получается, удаляет его и отправляет новое сообщение;
    - после этого очищает ui_state, чтобы следующий show_screen создал новый экран.
    """
    msg_id = await storage.get_ui_message_id(chat_id, user_id)

    if msg_id is not None:
        # больше не считаем это UI-сообщением
        await storage.clear_ui_message_id(chat_id, user_id)

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
            )
            return
        except TelegramBadRequest:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
        except Exception:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
    else:
        await storage.clear_ui_message_id(chat_id, user_id)

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        pass
