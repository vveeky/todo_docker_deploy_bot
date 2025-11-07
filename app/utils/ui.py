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
    Держит у пользователя в конкретном чате одно сообщение-UI:
    1) если есть прошлое UI-сообщение, пытается ОТРЕДАКТИРОВАТЬ его;
    2) если редактирование не удалось, пытается УДАЛИТЬ это сообщение;
    3) после этого отправляет НОВОЕ сообщение и запоминает его id.
    """
    if isinstance(event, CallbackQuery):
        await event.answer()
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
            # 1. попытка редактирования
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest:
            # 2. если редактировать нельзя — пробуем удалить
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except TelegramBadRequest:
                # уже удалено / нельзя удалить — идём дальше
                pass
            except Exception:
                pass
        except Exception:
            # любая другая ошибка при редактировании — тоже пробуем удалить
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass

    # 3. отправляем новое сообщение
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    _last_ui[key] = sent.message_id
