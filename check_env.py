#!/usr/bin/env python3
"""
Скрипт проверки конфигурации перед запуском бота
Запуск: python check_env.py
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os


def check_environment():
    """Проверка всех необходимых переменных окружения"""

    print("=" * 60)
    print("ДИАГНОСТИКА ОКРУЖЕНИЯ RICHMOND MARKET BOT")
    print("=" * 60)

    # 1. Проверка .env файла
    env_path = Path('.env')
    if env_path.exists():
        print(f"✓ .env файл найден: {env_path.absolute()}")
        load_dotenv(dotenv_path=env_path)
    else:
        print(f"✗ .env файл НЕ найден: {env_path.absolute()}")
        print("  Создайте файл .env на основе .env.example")
        return False

    # 2. Проверка критичных переменных
    required_vars = {
        'BOT_TOKEN': 'Токен Telegram бота',
        'ADMIN_ID': 'ID администратора',
        'TARGET_CHANNEL': 'Целевой канал (@channel)',
        'DB_HOST': 'Хост PostgreSQL',
        'DB_PORT': 'Порт PostgreSQL',
        'DB_NAME': 'Имя базы данных',
        'DB_USER': 'Пользователь БД',
        'DB_PASSWORD': 'Пароль БД',
    }

    print("\n" + "-" * 60)
    print("ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:")
    print("-" * 60)

    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Маскируем чувствительные данные
            if 'TOKEN' in var or 'PASSWORD' in var:
                masked = value[:8] + '***' if len(value) > 8 else '***'
                print(f"✓ {var:20} = {masked:30} ({description})")
            else:
                print(f"✓ {var:20} = {value:30} ({description})")
        else:
            print(f"✗ {var:20} = НЕ УСТАНОВЛЕНА!             ({description})")
            all_ok = False

    # 3. Проверка Redis (опционально)
    print("\n" + "-" * 60)
    print("ПРОВЕРКА REDIS (опционально, но рекомендуется):")
    print("-" * 60)

    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', '6379')

    try:
        import redis
        r = redis.Redis(host=redis_host, port=int(redis_port), db=0, socket_timeout=2)
        r.ping()
        print(f"✓ Redis доступен: {redis_host}:{redis_port}")
    except ImportError:
        print("⚠ Библиотека redis не установлена (pip install redis)")
    except Exception as e:
        print(f"⚠ Redis недоступен: {e}")
        print("  Бот будет использовать MemoryStorage (данные не сохраняются)")

    # 4. Проверка PostgreSQL
    print("\n" + "-" * 60)
    print("ПРОВЕРКА POSTGRESQL:")
    print("-" * 60)

    try:
        import asyncpg
        import asyncio

        async def check_db():
            try:
                conn = await asyncpg.connect(
                    host=os.getenv('DB_HOST'),
                    port=int(os.getenv('DB_PORT', 5432)),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    database=os.getenv('DB_NAME'),
                    timeout=5
                )
                await conn.close()
                return True
            except Exception as e:
                print(f"✗ Ошибка подключения к PostgreSQL: {e}")
                return False

        if asyncio.run(check_db()):
            print(f"✓ PostgreSQL доступен: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}")
        else:
            all_ok = False

    except ImportError:
        print("✗ Библиотека asyncpg не установлена (pip install asyncpg)")
        all_ok = False
    except Exception as e:
        print(f"✗ Ошибка проверки БД: {e}")
        all_ok = False

    # 5. Итоговый результат
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - бот готов к запуску")
        print("=" * 60)
        print("\nЗапустите бота: python main.py")
        return True
    else:
        print("✗ ОБНАРУЖЕНЫ ПРОБЛЕМЫ - исправьте их перед запуском")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = check_environment()
    sys.exit(0 if success else 1)