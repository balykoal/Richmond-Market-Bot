# Проверьте подключение к PostgreSQL через Python скрипт
# Создайте файл test_db_connection.py:

import asyncio
import asyncpg
import logging
from config import settings


async def test_connection():
    """Тест подключения к базе данных"""
    try:
        # Подключение к базе данных
        conn = await asyncpg.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME
        )

        print("✅ Подключение к базе данных успешно!")

        # Проверяем существующие таблицы
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)

        print(f"📊 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table['table_name']}")

        # Проверяем количество пользователей
        try:
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            print(f"👥 Пользователей в базе: {users_count}")
        except:
            print("⚠️ Таблица users не найдена")

        # Проверяем количество постов
        try:
            posts_count = await conn.fetchval("SELECT COUNT(*) FROM posts")
            print(f"📝 Постов в базе: {posts_count}")
        except:
            print("⚠️ Таблица posts не найдена")

        # Проверяем количество платежей
        try:
            payments_count = await conn.fetchval("SELECT COUNT(*) FROM payments")
            print(f"💳 Платежей в базе: {payments_count}")
        except:
            print("⚠️ Таблица payments не найдена")

        await conn.close()

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте, запущен ли PostgreSQL:")
        print("   - Windows: Диспетчер задач -> Службы -> postgresql")
        print("   - Linux: sudo systemctl status postgresql")
        print("   - macOS: brew services list | grep postgresql")
        print("\n2. Проверьте настройки в .env файле:")
        print(f"   DB_HOST={settings.DB_HOST}")
        print(f"   DB_PORT={settings.DB_PORT}")
        print(f"   DB_USER={settings.DB_USER}")
        print(f"   DB_NAME={settings.DB_NAME}")
        print("\n3. Попробуйте подключиться через psql:")
        print(f"   psql -h {settings.DB_HOST} -p {settings.DB_PORT} -U {settings.DB_USER} -d {settings.DB_NAME}")


if __name__ == "__main__":
    asyncio.run(test_connection())