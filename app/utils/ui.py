# app/utils/ui.py
from typing import Dict, Optional, Union, Tuple

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

# (chat_id, user_id) -> last ui message id
_last_ui: Dict[Tuple[int, int], int] = {}


async def show_screen(
    event: Union[Message, CallbackQuery],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """
    Держит у пользователя в конкретном чате одно сообщение UI:
    1) если есть прошлое UI-сообщение, пытается отредактировать его;
    2) если редактирование не удалось, пытается удалить это сообщение;
    3) после этого отправляет новое сообщение и запоминает его id.
    """
    if isinstance(event, CallbackQuery):
        bot: Bot = event.bot
        user_id = event.from_user.id
        chat_id = event.message.chat.id
    else:
        bot: Bot = event.bot
        user_id = event.from_user.id
        chat_id = event.chat.id

    key = (chat_id, user_id)
    msg_id = _last_ui.get(key)

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
    _last_ui[key] = sent.message_id

async def show_notification(
    bot: Bot,
    chat_id: int,
    user_id: int,
    text: str,
) -> None:
    """
    Показывает уведомление поверх текущего UI:
    - пытается отредактировать последнее UI-сообщение;
    - если не получается, удаляет его и шлёт новое;
    - после этого забывает это сообщение как UI, чтобы
      следующее show_screen создало новый экран.
    """
    key = (chat_id, user_id)
    msg_id = _last_ui.pop(key, None)

    if msg_id is not None:
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

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        pass
