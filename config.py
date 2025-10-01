"""
Конфигурация проекта Richmond Market
Настройки загружаются из переменных окружения
"""

from pydantic import validator
from pydantic_settings import BaseSettings
from pathlib import Path

# Определяем базовую папку проекта
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """
    Основные настройки приложения
    Все параметры загружаются из переменных окружения или .env файла
    """

    # Настройки Telegram Bot
    BOT_TOKEN: str
    ADMIN_ID: int
    TARGET_CHANNEL: str

    # Настройки базы данных PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str

    # Настройки Redis (опционально)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Настройки платежей
    CARD_NUMBER: str = "1234567890123456"
    CARD_HOLDER: str = "Иван Иванов"

    # Настройки приложения
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Настройки постов
    REGULAR_POST_PRICE: int = 200  # Цена обычного поста в рублях
    PINNED_POST_PRICE: int = 1000  # Цена закрепленного поста в рублях
    MIN_PHOTOS: int = 3  # Минимальное количество фото
    MAX_PHOTOS: int = 10  # Максимальное количество фото
    PAYMENT_CHECK_INTERVAL: int = 300  # Интервал проверки платежей в секундах (5 минут)

    # Настройки Тинькофф эквайринга
    TINKOFF_TERMINAL_KEY: str = "your_terminal_key"
    TINKOFF_PASSWORD: str = "your_password"
    TINKOFF_API_URL: str = "https://securepay.tinkoff.ru/v2"

    # Общие настройки платежей
    PAYMENT_PROVIDER: str = "tinkoff"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


    @validator("BOT_TOKEN")
    def validate_bot_token(cls, v):
        """Валидация токена бота"""
        if not v or len(v) < 10:
            raise ValueError("Некорректный BOT_TOKEN")
        return v

    @validator("TARGET_CHANNEL")
    def validate_channel(cls, v):
        """Валидация канала"""
        if not v.startswith("@"):
            raise ValueError("Канал должен начинаться с @")
        return v

    @property
    def database_url(self) -> str:
        """URL для подключения к PostgreSQL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def async_database_url(self) -> str:
        """Асинхронный URL для подключения к PostgreSQL"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> str:
        """URL для подключения к Redis"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        """Настройки pydantic"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Создаем глобальный объект настроек
settings = Settings()


# Типы постов
class PostType:
    """Константы типов постов"""
    REGULAR = "regular"  # Обычный пост
    PINNED = "pinned"  # Закрепленный пост


# Способы оплаты
class PaymentMethod:
    """Константы способов оплаты"""
    SBP = "sbp"  # Система быстрых платежей
    CRYPTO = "crypto"  # Криптовалюта


# Статусы платежей
class PaymentStatus:
    """Константы статусов платежей"""
    PENDING = "pending"  # Ожидает оплаты
    CHECKING = "checking"  # На проверке
    CONFIRMED = "confirmed"  # Подтвержден
    REJECTED = "rejected"  # Отклонен
    EXPIRED = "expired"  # Истек


# Статусы постов
class PostStatus:
    """Константы статусов постов"""
    DRAFT = "draft"  # Черновик
    PUBLISHED = "published"  # Опубликован
    ARCHIVED = "archived"  # Архивирован


# Состояния товара
class ItemCondition:
    """Константы состояния товара"""
    NEW = "new"  # Новое
    USED = "used"  # Б/у


# Настройки логирования
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': settings.LOG_LEVEL,
            'formatter': 'default',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': BASE_DIR / 'logs' / 'bot.log',
            'mode': 'a',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'aiogram': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
        },
        'bot': {
            'level': settings.LOG_LEVEL,
            'handlers': ['console', 'file'],
        },
    },
    'root': {
        'level': settings.LOG_LEVEL,
        'handlers': ['console', 'file'],
    },
}