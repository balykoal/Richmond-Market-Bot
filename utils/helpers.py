"""
Вспомогательные функции для бота
Утилиты общего назначения
"""

import logging
from datetime import datetime
from typing import List, Dict
from aiogram.types import PhotoSize, InputMediaPhoto, User

from config import settings, PostType, PaymentMethod, ItemCondition

logger = logging.getLogger(__name__)


class MessageFormatter:
    """Класс для форматирования сообщений"""

    @staticmethod
    def format_post_info(post_data: Dict) -> str:
        """
        Форматирование информации о посте для пользователя

        Args:
            post_data: Данные поста

        Returns:
            Отформатированный текст
        """
        condition_text = "✨ Новое" if post_data['condition'] == ItemCondition.NEW else "🔄 Б/у"
        post_type_text = "📌 Закрепленный" if post_data['post_type'] == PostType.PINNED else "📝 Обычный"

        text = f"""
📦 <b>{post_data['title']}</b>

{condition_text}
{post_type_text}

💰 <b>Цена:</b> {PriceHelper.format_price(post_data['price'])} ₽

📝 <b>Описание:</b>
{post_data['description']}

📞 <b>Контакты:</b> {post_data['contact_info']}

🕒 <i>Создан:</i> {TimeHelper.format_datetime(post_data['created_at'])}
        """

        return text.strip()

    @staticmethod
    def format_payment_info(payment_data: Dict, user_data: Dict) -> str:
        """
        Форматирование информации о платеже

        Args:
            payment_data: Данные платежа
            user_data: Данные пользователя

        Returns:
            Отформатированный текст
        """
        method_text = "🏦 СБП" if payment_data['method'] == PaymentMethod.SBP else "₿ Криптовалюта"

        text = f"""
💳 <b>Платеж #{payment_data['payment_id']}</b>

👤 <b>Пользователь:</b> {UserHelper.format_user_info(user_data)}
💰 <b>Сумма:</b> {PriceHelper.format_price(payment_data['amount'])} {payment_data['currency']}
🔄 <b>Способ:</b> {method_text}
📅 <b>Создан:</b> {TimeHelper.format_datetime(payment_data['created_at'])}
        """

        return text.strip()

    @staticmethod
    def format_admin_stats(stats: Dict) -> str:
        """
        Форматирование статистики для админа

        Args:
            stats: Статистика системы

        Returns:
            Отформатированный текст
        """
        text = f"""
📊 <b>Статистика системы</b>

👥 <b>Пользователи:</b>
├ Всего: {stats['users']['total']}
└ Новых сегодня: {stats['users']['new_today']}

📝 <b>Посты:</b>
├ Всего: {stats['posts']['total']}
├ Опубликованных: {stats['posts']['published']}
└ Сегодня создано: {stats['posts']['today']}

💰 <b>Платежи:</b>
├ Всего: {stats['payments']['total']}
├ Подтвержденных: {stats['payments']['confirmed']}
├ На проверке: {stats['payments']['pending']}
└ Общий доход: {PriceHelper.format_price(stats['payments']['revenue'])} ₽
        """

        return text.strip()


class TimeHelper:
    """Вспомогательные функции для работы со временем"""

    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """
        Форматирование даты и времени

        Args:
            dt: Объект datetime

        Returns:
            Отформатированная строка
        """
        if not dt:
            return "Не указано"

        return dt.strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def get_time_ago(dt: datetime) -> str:
        """
        Получение текста "время назад"

        Args:
            dt: Объект datetime

        Returns:
            Строка вида "5 минут назад"
        """
        if not dt:
            return "Неизвестно"

        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days} дн. назад"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ч. назад"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} мин. назад"
        else:
            return "Только что"


class MediaHelper:
    """Вспомогательные функции для работы с медиа"""

    @staticmethod
    def get_largest_photo(photos: List[PhotoSize]) -> PhotoSize:
        """
        Получение фотографии наибольшего размера

        Args:
            photos: Список размеров фотографии

        Returns:
            Фотография наибольшего размера
        """
        if not photos:
            return None

        return max(photos, key=lambda p: p.file_size or 0)

    @staticmethod
    def create_media_group(photo_ids: List[str]) -> List[InputMediaPhoto]:
        """
        Создание медиа-группы для отправки

        Args:
            photo_ids: Список ID фотографий

        Returns:
            Список InputMediaPhoto
        """
        if not photo_ids:
            return []

        media_group = []
        for photo_id in photo_ids:
            media_group.append(InputMediaPhoto(media=photo_id))

        return media_group


class UserHelper:
    """Вспомогательные функции для работы с пользователями"""

    @staticmethod
    def format_user_info(user_data: Dict) -> str:
        """
        Форматирование информации о пользователе

        Args:
            user_data: Данные пользователя

        Returns:
            Отформатированная строка
        """
        parts = []

        if user_data.get('first_name'):
            parts.append(user_data['first_name'])

        if user_data.get('last_name'):
            parts.append(user_data['last_name'])

        name = " ".join(parts) if parts else "Без имени"

        if user_data.get('username'):
            return f"{name} (@{user_data['username']})"
        else:
            return f"{name} (ID: {user_data['user_id']})"

    @staticmethod
    def extract_user_data(user: User) -> Dict:
        """
        Извлечение данных пользователя из объекта User

        Args:
            user: Объект пользователя Telegram

        Returns:
            Словарь с данными пользователя
        """
        return {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_bot': user.is_bot,
            'language_code': user.language_code
        }


class PriceHelper:
    """Вспомогательные функции для работы с ценами"""

    @staticmethod
    def format_price(price: float) -> str:
        """
        Форматирование цены

        Args:
            price: Цена

        Returns:
            Отформатированная строка
        """
        if price == int(price):
            return f"{int(price):,}".replace(',', ' ')
        else:
            return f"{price:,.2f}".replace(',', ' ')

    @staticmethod
    def get_post_price(post_type: str) -> int:
        """
        Получение цены за пост

        Args:
            post_type: Тип поста

        Returns:
            Цена в рублях
        """
        if post_type == PostType.PINNED:
            return settings.PINNED_POST_PRICE
        else:
            return settings.REGULAR_POST_PRICE


class TextHelper:
    """Вспомогательные функции для работы с текстом"""

    @staticmethod
    def truncate_text(text: str, max_length: int = 50) -> str:
        """
        Обрезка текста до указанной длины

        Args:
            text: Исходный текст
            max_length: Максимальная длина

        Returns:
            Обрезанный текст
        """
        if not text:
            return ""

        if len(text) <= max_length:
            return text

        return text[:max_length-3] + "..."

    @staticmethod
    def escape_html(text: str) -> str:
        """
        Экранирование HTML символов

        Args:
            text: Исходный текст

        Returns:
            Экранированный текст
        """
        if not text:
            return ""

        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))


# Глобальные вспомогательные функции
def format_price(price: float) -> str:
    """Форматирование цены"""
    return PriceHelper.format_price(price)


def format_datetime(dt: datetime) -> str:
    """Форматирование даты и времени"""
    return TimeHelper.format_datetime(dt)


def format_user_info(user_data: Dict) -> str:
    """Форматирование информации о пользователе"""
    return UserHelper.format_user_info(user_data)


async def send_notification_to_admin(bot, message: str) -> bool:
    """
    Отправка уведомления администратору

    Args:
        bot: Объект бота
        message: Текст сообщения

    Returns:
        True если отправлено успешно
    """
    try:
        await bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=f"🔔 <b>Уведомление</b>\n\n{message}",
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")
        return False


async def log_error(error: Exception, context: str = None) -> None:
    """
    Логирование ошибки

    Args:
        error: Объект исключения
        context: Контекст ошибки
    """
    error_msg = f"Ошибка"
    if context:
        error_msg += f" в {context}"
    error_msg += f": {str(error)}"

    logger.error(error_msg, exc_info=True)