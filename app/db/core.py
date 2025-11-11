# app/db/core.py
import os
import logging
import secrets
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.pool.Pool] = None


async def init_db_and_schema() -> None:
    """
    Поднимает пул соединений и создаёт таблицы, если их ещё нет.
    Вызывать один раз при старте приложения.
    """
    global _pool
    if _pool is not None:
        return

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL не задан. Укажи его в .env")

    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    logger.info("Postgres pool создан")

    async with _pool.acquire() as conn:
        # таблица задач + состояния
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_state (
                user_id   BIGINT    NOT NULL,
                task_id   INTEGER   NOT NULL,
                is_done   BOOLEAN   NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                due_at    TIMESTAMPTZ,
                PRIMARY KEY (user_id, task_id)
            );
            """
        )

        # гарантируем наличие столбца text для хранения текста задачи
        await conn.execute(
            """
            ALTER TABLE task_state
            ADD COLUMN IF NOT EXISTS text TEXT NOT NULL DEFAULT '';
            """
        )

        # таблица ui-состояния (id экранного сообщения)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_state (
                user_id    BIGINT NOT NULL,
                chat_id    BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                PRIMARY KEY (user_id, chat_id)
            );
            """
        )

        # таблица настроек пользователей (часовой пояс + веб-токен)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id          BIGINT PRIMARY KEY,
                tz_offset_minutes INTEGER NOT NULL DEFAULT 0
            );
            """
        )

        await conn.execute(
            """
            ALTER TABLE user_settings
            ADD COLUMN IF NOT EXISTS web_token TEXT UNIQUE,
            ADD COLUMN IF NOT EXISTS web_token_rotated_at TIMESTAMPTZ;
            """
        )

    logger.info("Схема БД проверена/создана")


async def get_pool() -> asyncpg.pool.Pool:
    if _pool is None:
        raise RuntimeError("DB не инициализирован. Сначала вызови init_db_and_schema()")
    return _pool


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_user_tz_offset(user_id: int) -> Optional[int]:
    """
    Возвращает смещение в минутах или None, если пользователь ещё не настраивал время.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tz_offset_minutes FROM user_settings WHERE user_id = $1",
            user_id,
        )
    if row is None:
        return None
    return row["tz_offset_minutes"]


async def set_user_tz_offset(user_id: int, offset_minutes: int) -> None:
    """
    Сохраняет/обновляет смещение в минутах для пользователя.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, tz_offset_minutes)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
            SET tz_offset_minutes = EXCLUDED.tz_offset_minutes
            """,
            user_id,
            offset_minutes,
        )


WEB_TOKEN_BYTES = 32  # минимум 32 байта энтропии


def _generate_web_token() -> str:
    # URL-safe base64, энтропия >= 32 bytes
    return secrets.token_urlsafe(WEB_TOKEN_BYTES)


async def get_or_create_web_token(user_id: int) -> str:
    """
    Вернёт существующий web_token пользователя или создаст новый.
    """
    global _pool
    async with _pool.acquire() as conn:  # type: ignore[union-attr]
        row = await conn.fetchrow(
            "SELECT web_token FROM user_settings WHERE user_id = $1",
            user_id,
        )
        if row and row["web_token"]:
            return row["web_token"]

        token = _generate_web_token()
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, web_token, web_token_rotated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET web_token = EXCLUDED.web_token,
                web_token_rotated_at = EXCLUDED.web_token_rotated_at
            """,
            user_id,
            token,
        )
        return token


async def rotate_web_token(user_id: int) -> str:
    """
    Всегда создаёт новый web_token, старый становится невалидным.
    """
    global _pool
    token = _generate_web_token()
    async with _pool.acquire() as conn:  # type: ignore[union-attr]
        await conn.execute(
            """
            UPDATE user_settings
            SET web_token = $2,
                web_token_rotated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            token,
        )
    return token


async def get_user_id_by_token(token: str) -> Optional[int]:
    """
    Находит user_id по токену. Если токен не найден — None.
    """
    if not token:
        return None

    global _pool
    async with _pool.acquire() as conn:  # type: ignore[union-attr]
        row = await conn.fetchrow(
            "SELECT user_id FROM user_settings WHERE web_token = $1",
            token,
        )
    return int(row["user_id"]) if row else None
