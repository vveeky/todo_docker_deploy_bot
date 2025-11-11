# app/states/time_settings.py
from aiogram.fsm.state import StatesGroup, State


class TimeSettingsStates(StatesGroup):
    waiting_for_time = State()
