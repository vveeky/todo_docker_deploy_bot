# app/keyboards/tasks_kb.py
from typing import List, Dict

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

DEFAULT_PER_PAGE = 5
PREVIEW_WORDS = 6


def _preview(text: str, words: int = PREVIEW_WORDS) -> str:
    parts = text.strip().split()
    if len(parts) <= words:
        return text
    return " ".join(parts[:words]) + "…"


def tasks_page_keyboard(
    tasks: List[Dict], page: int = 0, per_page: int = DEFAULT_PER_PAGE
) -> InlineKeyboardMarkup:
    total = len(tasks)
    if total == 0:
        return InlineKeyboardMarkup(inline_keyboard=[])

    total_pages = (total + per_page - 1) // per_page
    if page < 0:
        page = 0
    if page > total_pages - 1:
        page = total_pages - 1

    start = page * per_page
    end = start + per_page
    page_items = tasks[start:end]

    rows: List[List[InlineKeyboardButton]] = []

    for t in page_items:
        tid = t.get("id")
        label = f"{tid}. {_preview(t.get('text', ''))}"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"task:show:{tid}")]
        )

    prev_cb = f"tasks:page:{page - 1}" if page > 0 else "noop"
    next_cb = f"tasks:page:{page + 1}" if page < total_pages - 1 else "noop"
    prev_text = "⬅️" if page > 0 else " "
    next_text = "➡️" if page < total_pages - 1 else " "
    center_text = f"{page + 1}/{total_pages}"

    rows.append(
        [
            InlineKeyboardButton(text=prev_text, callback_data=prev_cb),
            InlineKeyboardButton(text=center_text, callback_data=f"tasks:page:{page}"),
            InlineKeyboardButton(text=next_text, callback_data=next_cb),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(text="Отложить до…", callback_data="tasks:postpone_prompt"),
            InlineKeyboardButton(text="Режим удаления", callback_data="tasks:delete_mode"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
