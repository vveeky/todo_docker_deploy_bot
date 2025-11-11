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
    event: Message | CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    """
    Универсальный экран бота.
    Логика:
      - если есть сохранённый message_id в ui_state -> пытаемся отредактировать его;
      - если редактирование не удалось или id нет -> отправляем новое сообщение и сохраняем id.
    """
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
        bot: Bot = event.message.bot
        chat_id = message.chat.id
        user_id = event.from_user.id
    else:
        message = event
        bot: Bot = event.bot
        chat_id = message.chat.id
        user_id = message.from_user.id

    msg_id = await storage.get_ui_message_id(chat_id, user_id)

    # Пытаемся отредактировать существующий экран
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
            # сообщение не найдено / не редактируемо -> считаем, что id устарел
            msg_id = None
        except Exception:
            # чтобы не ломать бота из-за экрана, просто сбросим id и отправим новый
            msg_id = None

    # Если нет валидного message_id -> отправляем новый экран и запоминаем его
    try:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )
    except Exception:
        # если даже отправка экрана не удалась, дальше делать нечего
        return

    try:
        await storage.save_ui_message_id(chat_id, user_id, sent.message_id)
    except Exception:
        # если не смогли сохранить id, просто живём без него
        pass



async def show_notification(
    bot: Bot,
    chat_id: int,
    user_id: int,
    text: str,
) -> None:
    """
    Уведомление от нотифаера:
      - сначала пытается отредактировать текущий UI-экран (если есть);
      - если не получилось, просто отправляет отдельное сообщение;
      - ui_state НЕ трогаем (message_id для главного экрана не сбрасываем).
    """
    msg_id = await storage.get_ui_message_id(chat_id, user_id)

    if msg_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
            )
            return
        except TelegramBadRequest:
            # экран исчез или не редактируется — просто отправим новое уведомление
            pass
        except Exception:
            pass

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        # уведомление не критично — глушим ошибку
        pass
