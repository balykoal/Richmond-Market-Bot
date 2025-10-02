"""
Модуль для подключения к PostgreSQL
Асинхронная работа с базой данных через asyncpg
"""

import asyncpg
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from config import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений
_connection_pool: Optional[asyncpg.Pool] = None

async def init_connection(conn):
    """
    Функция инициализации каждого подключения в пуле
    Устанавливает правильную кодировку для работы с UTF-8
    """
    # Устанавливаем кодировку подключения
    try:
        await conn.execute("SET client_encoding TO 'UTF8'")
        await conn.execute("SET timezone TO 'UTC'")
        logger.debug("Подключение к БД настроено: UTF8, UTC")
    except Exception as e:
        logger.error(f"Ошибка настройки подключения к БД: {e}")
        raise

async def init_db() -> None:
    """
    Инициализация подключения к базе данных
    Создание пула соединений и таблиц
    """
    global _connection_pool

    try:
        # Создание пула соединений
        _connection_pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            min_size=5,
            max_size=20,
            init=init_connection,
            command_timeout=60
        )
        logger.info("Подключение к базе данных установлено")

        # Создание таблицы
        await create_tables()
        logger.info("Таблицы созданы успешно")

    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        raise


async def close_db() -> None:
    """
    Закрытие соединения с базой данных
    """
    global _connection_pool

    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None
        logger.info("Соединение с базой данных закрыто")


@asynccontextmanager
async def get_connection():
    """
    Контекстный менеджер для получения соединения из пула
    """
    if not _connection_pool:
        raise RuntimeError("База данных не инициализирована")

    connection = await _connection_pool.acquire()
    try:
        yield connection
    finally:
        await _connection_pool.release(connection)


async def create_tables() -> None:
    """
    Создание всех таблиц в базе данных
    """
    async with get_connection() as conn:
        # Таблица пользователей
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                phone VARCHAR(20),
                reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                balance DECIMAL(10,2) DEFAULT 0.00,
                is_blocked BOOLEAN DEFAULT FALSE,
                post_count INTEGER DEFAULT 0
            )
        """)

        # Таблица постов
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                photos TEXT[] NOT NULL,
                title VARCHAR(255) NOT NULL,
                condition VARCHAR(20) NOT NULL,
                description TEXT NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                contact_info TEXT NOT NULL,
                post_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'draft',
                message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                is_pinned BOOLEAN DEFAULT FALSE
            )
        """)

        # Таблица платежей
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                post_id INTEGER REFERENCES posts(post_id),
                amount DECIMAL(10,2) NOT NULL,
                currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
                method VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                transaction_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                confirmed_by BIGINT,
                rejection_reason TEXT
            )
        """)

        #Оферта
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            phone VARCHAR(20),
            reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            balance DECIMAL(10,2) DEFAULT 0.00,
            is_blocked BOOLEAN DEFAULT FALSE,
            post_count INTEGER DEFAULT 0,
            offer_accepted BOOLEAN DEFAULT FALSE,
            offer_accepted_at TIMESTAMP
        )
        """)

        # Таблица логов администратора
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                log_id SERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                action VARCHAR(100) NOT NULL,
                details JSONB,
                target_user_id BIGINT,
                target_payment_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица для чеков
        await conn.execute("""
                    CREATE TABLE IF NOT EXISTS receipts (
                        receipt_id SERIAL PRIMARY KEY,
                        payment_id INTEGER NOT NULL REFERENCES payments(payment_id),
                        user_id BIGINT NOT NULL REFERENCES users(user_id),
                        admin_id BIGINT NOT NULL,
                        file_id VARCHAR(500),
                        file_type VARCHAR(50),
                        file_name VARCHAR(255),
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT
                    )
                """)

        # Идексы для оптимизации запросов
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_logs_admin_id ON admin_logs(admin_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_payment ON receipts(payment_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_user ON receipts(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_admin ON receipts(admin_id)")



async def execute_query(query: str, *args) -> Any:
    """
    Выполнение SQL запроса

    Args:
        query: SQL запрос
        *args: Параметры запроса

    Returns:
        Результат выполнения запроса
    """
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def execute_query_one(query: str, *args) -> Optional[Dict]:
    """
    Выполнение SQL запроса с возвращением одной записи

    Args:
        query: SQL запрос
        *args: Параметры запроса

    Returns:
        Одна запись или None
    """
    async with get_connection() as conn:
        result = await conn.fetchrow(query, *args)
        return dict(result) if result else None


async def execute_command(query: str, *args) -> str:
    """
    Выполнение команды SQL (INSERT, UPDATE, DELETE)

    Args:
        query: SQL команда
        *args: Параметры команды

    Returns:
        Статус выполнения команды
    """
    async with get_connection() as conn:
        return await conn.execute(query, *args)