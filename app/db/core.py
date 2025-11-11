# app/db/core.py
import os
import logging
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
        # таблица состояний задач
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_state (
                user_id    BIGINT NOT NULL,
                task_id    INTEGER NOT NULL,
                is_done    BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                due_at     TIMESTAMPTZ,
                PRIMARY KEY (user_id, task_id)
            );
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
