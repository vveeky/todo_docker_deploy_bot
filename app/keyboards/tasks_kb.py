# app/keyboards/tasks_kb.py
from typing import List, Dict, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

DEFAULT_PER_PAGE = 5


def tasks_page_keyboard(
    tasks_sorted: List[Dict],
    page: int,
    per_page: int = DEFAULT_PER_PAGE,
    site_url: Optional[str] = None,
) -> InlineKeyboardMarkup:

    """
    Строит клавиатуру для списка задач:
    - нумерация задач в UI: 1..N по позиции в общем отсортированном списке;
    - колбэки используют реальные внутренние id задач;
    - есть навигация по страницам;
    - есть кнопка "Режим удаления";
    - есть кнопка "Команды" (cmd_help).
    """
    total = len(tasks_sorted)
    if per_page <= 0:
        per_page = DEFAULT_PER_PAGE

    # диапазон задач для текущей страницы
    start_index = page * per_page
    end_index = min(start_index + per_page, total)

    rows: List[List[InlineKeyboardButton]] = []

    # задачи текущей страницы
    for visible_index, task in enumerate(
        tasks_sorted[start_index:end_index],
        start=start_index + 1,  # глобальная нумерация 1..N
    ):
        tid = task.get("id")
        text = task.get("text", "") or ""
        mark = "✅" if task.get("is_done") else "✳️"
        label = f"{visible_index}. {mark} {text[:40]}"

        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"task:show:{tid}",
                )
            ]
        )

    # навигация по страницам
    nav_row: List[InlineKeyboardButton] = []

    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"tasks:page:{page - 1}",
            )
        )

    if end_index < total:
        nav_row.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"tasks:page:{page + 1}",
            )
        )

    if nav_row:
        rows.append(nav_row)

    
    rows.append(
        [
            InlineKeyboardButton(
                text="Добавить задачу ➕",
                callback_data="cmd_add",
            )
        ]
    )

        # кнопка открытия сайта (если передали URL)
    if site_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🌐 Открыть сайт",
                    web_app=WebAppInfo(url=site_url),
                )
            ]
        )


    # режим удаления
    rows.append(
        [
            InlineKeyboardButton(
                text="Режим удаления",
                callback_data="tasks:delete_mode",
            )
        ]
    )

    # выход к командам (существующий колбэк cmd_help)
    rows.append(
        [
            InlineKeyboardButton(
                text="Назад к командам",
                callback_data="cmd_help",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
