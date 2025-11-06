# app/bot.py
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment")

bot = Bot(token=TOKEN)
dp = Dispatcher()
