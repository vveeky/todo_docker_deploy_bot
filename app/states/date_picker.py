# app/states/date_picker.py
from aiogram.fsm.state import StatesGroup, State


class DatePickerState(StatesGroup):
    picking = State()
