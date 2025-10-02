"""
Главный файл запуска бота Richmond Market
Инициализация и запуск всех компонентов системы
"""

import asyncio
import logging.config
import sys
import io
from pathlib import Path


# Устанавливаем кодировку UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings, LOGGING_CONFIG
from database import init_db, close_db
from handlers import register_handlers
from services.backup_scheduler import BackupScheduler
from services.notification import NotificationService
from utils.middleware import DatabaseMiddleware, AdminMiddleware, ThrottlingMiddleware, ErrorHandlingMiddleware

# Создаем папку для логов
Path("logs").mkdir(exist_ok=True)

# Настраиваем логирование
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """
    Функция инициализации при запуске бота
    """
    try:
        # Инициализируем базу данных
        await init_db()
        logger.info("База данных инициализирована")

        # Проверяем подключение к боту
        bot_info = await bot.get_me()
        logger.info(f"Бот @{bot_info.username} готов к работе")

        # Проверяем права в целевом канале
        try:
            await bot.get_chat(settings.TARGET_CHANNEL)
            chat_member = await bot.get_chat_member(settings.TARGET_CHANNEL, bot_info.id)

            if not chat_member.can_post_messages:
                logger.warning("У бота нет прав на публикацию в целевом канале!")
            else:
                logger.info(f"Права в канале {settings.TARGET_CHANNEL} подтверждены")

        except Exception as err:
            logger.warning(f"Не удалось проверить права в канале: {err}")

        # Уведомляем админа о запуске
        try:
            await bot.send_message(
                chat_id=settings.ADMIN_ID,
                text="🟢 <b>Бот запущен!</b>\n\nВсе системы работают нормально.",
                parse_mode="HTML"
            )
        except Exception as ex:
            logger.warning(f"Не удалось отправить уведомление админу о запуске: {ex}")

        # Запускаем сервис уведомлений
        notification_service = NotificationService(bot)
        backup_scheduler = BackupScheduler(bot)
        asyncio.create_task(notification_service.start_payment_checker())
        logger.info("Сервис уведомлений запущен")

        setattr(bot, "backup_scheduler", backup_scheduler)
        asyncio.create_task(backup_scheduler.start_scheduler())
        logger.info("Планировщик бэкапов запущен")

        logger.info("Бот успешно запущен!")

    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)


async def on_shutdown(bot: Bot) -> None:
    """
    Функция завершения работы бота
    """
    try:
        # Уведомляем админа о завершении работы
        try:
            await bot.send_message(
                chat_id=settings.ADMIN_ID,
                text="🔴 <b>Бот остановлен!</b>\n\nВыполняется корректное завершение работы.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление админу о завершении: {e}")

        try:
            if hasattr(bot, "backup_scheduler"):
                bot.backup_scheduler.stop_scheduler()
                logger.info("Планировщик бэкапов остановлен")
        except Exception as e:
            logger.warning(f"Не удалось корректно остановить планировщик бэкапов: {e}")

        # Закрываем соединение с базой данных
        await close_db()
        logger.info("База данных отключена")

        logger.info("Бот корректно завершил работу")

    except Exception as e:
        logger.error(f"Ошибка при завершении работы бота: {e}")


async def main() -> None:
    """
    Главная функция запуска бота
    """
    try:
        logger.info("Запуск Richmond Market Bot...")

        # Создаем бота с настройками по умолчанию
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                protect_content=False
            )
        )

        try:
            storage = RedisStorage.from_url(settings.redis_url)
            logger.info("✓ Используется RedisStorage (данные сохраняются при перезапуске)")
        except Exception as redis_error:
            logger.warning(f"⚠ Redis недоступен: {redis_error}")
            logger.warning("⚠ Используется MemoryStorage - состояния FSM будут потеряны при перезапуске!")
            logger.warning("⚠ Рекомендуется установить и настроить Redis для production")
            storage = MemoryStorage()

        # Создаем диспетчер с хранилищем в памяти
        dp = Dispatcher(storage=storage)

        # Регистрируем middleware (порядок важен!)
        dp.message.middleware(ErrorHandlingMiddleware())
        dp.callback_query.middleware(ErrorHandlingMiddleware())

        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())

        dp.message.middleware(AdminMiddleware())
        dp.callback_query.middleware(AdminMiddleware())

        dp.message.middleware(ThrottlingMiddleware(limit=0.3))
        dp.callback_query.middleware(ThrottlingMiddleware(limit=0.2))

        # Регистрируем обработчики
        register_handlers(dp)
        logger.info("Обработчики зарегистрированы")

        # Регистрируем функции startup и shutdown
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Запускаем бота
        logger.info("Запускаем polling...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения работы")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)