import datetime as dt
from typing import Optional

def format_dt(iso_str: Optional[str]) -> str:
    """Форматирует ISO-строку даты в человекочитаемый вид."""
    if not iso_str:
        return "не установлено"
    try:
        dt_obj = dt.datetime.fromisoformat(iso_str)
        return dt_obj.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str