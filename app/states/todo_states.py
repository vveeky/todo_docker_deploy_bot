# app/states/todo_states.py
from aiogram.fsm.state import StatesGroup, State


class TodoStates(StatesGroup):
    add_text = State()
    edit_text = State()
    edit_due = State()
    postpone_wait_date = State()
