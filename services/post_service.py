"""
Сервис для работы с постами
Публикация, форматирование и управление постами в канале
"""

import logging
from typing import Tuple, Optional
from aiogram import Bot

from database import PostOperations, UserOperations
from utils.helpers import MediaHelper, format_price
from config import settings, PostType, ItemCondition

logger = logging.getLogger(__name__)


class PostService:
    """Сервис для работы с постами"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def publish_post(self, post_id: int) -> Tuple[bool, Optional[int]]:
        """
        Публикация поста в канале

        Args:
            post_id: ID поста в базе данных

        Returns:
            Кортеж (успех, ID сообщения в канале)
        """
        try:
            # Получаем данные поста
            post = await PostOperations.get_post(post_id)
            if not post:
                logger.error(f"Пост {post_id} не найден")
                return False, None

            # Получаем данные пользователя
            user = await UserOperations.get_user(post['user_id'])
            if not user:
                logger.error(f"Пользователь {post['user_id']} не найден")
                return False, None

            # Формируем текст поста
            post_text = self._format_channel_post(post, user)

            # Создаем медиа-группу с фотографиями
            media_group = MediaHelper.create_media_group(post['photos'])

            if not media_group:
                logger.error(f"Не удалось создать медиа-группу для поста {post_id}")
                return False, None

            # Добавляем текст к первой фотографии
            media_group[0].caption = post_text
            media_group[0].parse_mode = "HTML"

            # Отправляем медиа-группу в канал
            messages = await self.bot.send_media_group(
                chat_id=settings.TARGET_CHANNEL,
                media=media_group
            )

            if not messages:
                logger.error(f"Не удалось отправить медиа-группу для поста {post_id}")
                return False, None

            # Получаем ID первого сообщения
            main_message_id = messages[0].message_id

            # Закрепляем пост если это закрепленный тип
            if post['post_type'] == PostType.PINNED:
                try:
                    await self.bot.pin_chat_message(
                        chat_id=settings.TARGET_CHANNEL,
                        message_id=main_message_id,
                        disable_notification=True
                    )
                    logger.info(f"Пост {post_id} закреплен в канале")
                except Exception as e:
                    logger.warning(f"Не удалось закрепить пост {post_id}: {e}")

            logger.info(f"Пост {post_id} успешно опубликован (message_id: {main_message_id})")
            return True, main_message_id

        except Exception as e:
            logger.error(f"Ошибка публикации поста {post_id}: {e}")
            return False, None

    def _format_channel_post(self, post: dict, user: dict) -> str:
        """
        Форматирование текста поста для канала

        Args:
            post: Данные поста
            user: Данные пользователя

        Returns:
            Отформатированный текст
        """
        # Эмодзи для состояния товара
        condition_emoji = "✨" if post['condition'] == ItemCondition.NEW else "🔄"
        condition_text = "Новое" if post['condition'] == ItemCondition.NEW else "Б/у"

        # Эмодзи для типа поста
        type_emoji = "📌" if post['post_type'] == PostType.PINNED else "📝"

        # Форматируем цену
        price_text = format_price(post['price'])

        # Форматируем контактную информацию со ссылкой
        contact_info = self._format_contact_with_link(post['contact_info'])

        # Генерируем артикул на основе ID поста
        article_code = self._generate_article_code(post['post_id'])

        # Собираем текст поста
        text = f"""{type_emoji} <b>{post['title']}</b>

    {condition_emoji} <b>Состояние:</b> {condition_text}
    💰 <b>Цена:</b> {price_text} ₽

    📝 <b>Описание:</b>
    {post['description']}

    📞 <b>Связь с продавцом:</b>
    {contact_info}

    <b>────────────────</b>
    🏷 Артикул: {article_code} | @richmondmarket"""

        return text.strip()

    @staticmethod
    def _generate_article_code(post_id: int) -> str:
        """
        Генерирует красивый артикул на основе ID поста

        Args:
            post_id: ID поста

        Returns:
            Артикул в формате RM-XXX
        """
        # Создаем артикул в формате RM-001, RM-002, etc.
        return f"RM-{post_id:03d}"

    @staticmethod
    def _format_contact_with_link(contact_info: str) -> str:
        """
        Форматирует контактную информацию, создавая ссылки где возможно

        Args:
            contact_info: Исходная контактная информация

        Returns:
            Отформатированная контактная информация со ссылками
        """
        import re

        # Ищем username Telegram (начинается с @)
        username_pattern = r'@(\w+)'
        usernames = re.findall(username_pattern, contact_info)

        formatted_contact = contact_info

        # Заменяем найденные username на ссылки
        for username in usernames:
            old_text = f"@{username}"
            new_text = f'<a href="https://t.me/{username}">@{username}</a>'
            formatted_contact = formatted_contact.replace(old_text, new_text)

        # Ищем номера телефонов и делаем их кликабельными
        phone_pattern = r'(\+?\d[\d\s\-\(\)]{8,})'
        phones = re.findall(phone_pattern, contact_info)

        for phone in phones:
            # Убираем пробелы и скобки для ссылки
            clean_phone = re.sub(r'[\s\-()]', '', phone)
            if clean_phone.startswith('+') or len(clean_phone) >= 10:
                phone_link = f'<a href="tel:{clean_phone}">{phone}</a>'
                formatted_contact = formatted_contact.replace(phone, phone_link, 1)

        return formatted_contact

    @staticmethod
    async def get_post_statistics(post_id: int) -> dict:
        """
        Получение статистики поста

        Args:
            post_id: ID поста

        Returns:
            Словарь со статистикой
        """
        try:
            post = await PostOperations.get_post(post_id)
            if not post:
                return {}

            stats = {
                'post_id': post_id,
                'status': post['status'],
                'created_at': post['created_at'],
                'published_at': post.get('published_at'),
                'message_id': post.get('message_id'),
                'is_pinned': post['post_type'] == PostType.PINNED,
                'views': 0,  # TODO: Получение просмотров через Bot API
                'reactions': 0  # TODO: Получение реакций
            }

            return stats

        except Exception as e:
            logger.error(f"Ошибка получения статистики поста {post_id}: {e}")
            return {}

    async def delete_post(self, post_id: int) -> bool:
        """
        Удаление поста из канала

        Args:
            post_id: ID поста

        Returns:
            True если удален успешно
        """
        try:
            post = await PostOperations.get_post(post_id)
            if not post or not post.get('message_id'):
                logger.warning(f"Пост {post_id} не найден или не опубликован")
                return False

            # Удаляем сообщение из канала
            try:
                await self.bot.delete_message(
                    chat_id=settings.TARGET_CHANNEL,
                    message_id=post['message_id']
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение {post['message_id']}: {e}")

            # Обновляем статус в базе данных
            # TODO: Добавить метод для архивации поста

            logger.info(f"Пост {post_id} удален из канала")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления поста {post_id}: {e}")
            return False

    async def unpin_post(self, post_id: int) -> bool:
        """
        Открепление поста в канале

        Args:
            post_id: ID поста

        Returns:
            True если откреплен успешно
        """
        try:
            post = await PostOperations.get_post(post_id)
            if not post or not post.get('message_id'):
                return False

            await self.bot.unpin_chat_message(
                chat_id=settings.TARGET_CHANNEL,
                message_id=post['message_id']
            )

            logger.info(f"Пост {post_id} откреплен")
            return True

        except Exception as e:
            logger.error(f"Ошибка откепления поста {post_id}: {e}")
            return False

    @staticmethod
    async def edit_post(post_id: int, updates) -> bool:
        """
        Редактирование поста в канале

        Args:
            post_id: ID поста
            **updates: Обновляемые поля

        Returns:
            True если обновлен успешно
        """
        try:
            # TODO: Реализовать редактирование поста в канале
            # Сложность: Telegram не позволяет редактировать медиа-группы
            # Возможные решения:
            # 1. Удалить старый пост и создать новый
            # 2. Отправить исправленную информацию отдельным сообщением

            logger.info(f"Редактирование поста {post_id} (функция в разработке)")
            return True

        except Exception as e:
            logger.error(f"Ошибка редактирования поста {post_id}: {e}")
            return False

    @staticmethod
    def _validate_post_data(post: dict) -> bool:
        """
        Валидация данных поста перед публикацией

        Args:
            post: Данные поста

        Returns:
            True если данные валидны
        """
        required_fields = ['title', 'description', 'price', 'contact_info', 'photos']

        for field in required_fields:
            if not post.get(field):
                logger.error(f"Отсутствует обязательное поле: {field}")
                return False

        # Проверка фотографий
        if len(post['photos']) < settings.MIN_PHOTOS:
            logger.error(f"Недостаточно фотографий: {len(post['photos'])} < {settings.MIN_PHOTOS}")
            return False

        if len(post['photos']) > settings.MAX_PHOTOS:
            logger.error(f"Слишком много фотографий: {len(post['photos'])} > {settings.MAX_PHOTOS}")
            return False

        # Проверка цены
        if post['price'] <= 0:
            logger.error(f"Неверная цена: {post['price']}")
            return False

        return True