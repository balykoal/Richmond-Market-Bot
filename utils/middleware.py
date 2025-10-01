"""
Middleware для бота
Промежуточное ПО для обработки запросов
"""

import logging
from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from database import UserOperations
from utils.helpers import UserHelper, send_notification_to_admin
from config import settings

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для автоматической регистрации пользователей
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        """
        Обработка события с автоматической регистрацией пользователя

        Args:
            handler: Следующий обработчик
            event: Событие (Message или CallbackQuery)
            data: Данные события

        Returns:
            Результат обработки
        """
        try:
            user = event.from_user

            if user and not user.is_bot:
                # Извлекаем данные пользователя
                user_data = UserHelper.extract_user_data(user)

                # Проверяем, существует ли пользователь
                existing_user = await UserOperations.get_user(user.id)
                if not existing_user:
                    # Создаем нового пользователя
                    success = await UserOperations.create_user(
                        user_id=user_data['user_id'],
                        username=user_data['username'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name']
                    )

                    if success:
                        logger.info(f"Автоматически зарегистрирован пользователь {user.id}")

                        # Уведомляем админа о новом пользователе
                        from utils.helpers import format_user_info
                        await send_notification_to_admin(
                            data.get('bot'),  # Получаем бота из данных
                            f"👋 Новый пользователь: {format_user_info(user_data)}"
                        )
                else:
                    # Обновляем информацию о пользователе если изменилась
                    if (existing_user.get('username') != user.username or
                        existing_user.get('first_name') != user.first_name or
                        existing_user.get('last_name') != user.last_name):

                        await UserOperations.create_user(
                            user_id=user_data['user_id'],
                            username=user_data['username'],
                            first_name=user_data['first_name'],
                            last_name=user_data['last_name']
                        )

                        logger.info(f"Обновлены данные пользователя {user.id}")

                # Добавляем данные пользователя в контекст
                data['user_data'] = user_data
                data['db_user'] = existing_user or user_data

            # Продолжаем обработку
            return await handler(event, data)

        except Exception as e:
            logger.error(f"Ошибка в DatabaseMiddleware: {e}")
            # Продолжаем обработку даже при ошибке
            return await handler(event, data)


class AdminMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        """
        Проверка прав администратора

        Args:
            handler: Следующий обработчик
            event: Событие
            data: Данные события

        Returns:
            Результат обработки
        """
        try:
            user = event.from_user

            # Добавляем флаг админа в контекст
            data['is_admin'] = user and user.id == settings.ADMIN_ID

            # Логируем действия админа
            if data['is_admin']:
                action_text = None

                if isinstance(event, Message):
                    if event.text and event.text.startswith('/'):
                        action_text = f"Команда: {event.text}"
                    elif event.text:
                        action_text = f"Сообщение: {event.text[:50]}..."
                    elif event.photo:
                        action_text = "Фото"
                    elif event.document:
                        action_text = "Документ"
                elif isinstance(event, CallbackQuery):
                    action_text = f"Callback: {event.data}"

                if action_text:
                    logger.info(f"Админ {user.id}: {action_text}")

            return await handler(event, data)

        except Exception as e:
            logger.error(f"Ошибка в AdminMiddleware: {e}")
            return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов (защита от спама)
    """

    def __init__(self, limit: float = 1.0):
        """
        Инициализация middleware

        Args:
            limit: Минимальный интервал между сообщениями в секундах
        """
        self.limit = limit
        self.user_timings: Dict[int, float] = {}
        self.media_groups: Dict[str, float] = {}  # Отслеживание медиагрупп

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: Union[Message, CallbackQuery],
            data: Dict[str, Any],
    ) -> Any:
        """
        Проверка частоты запросов с исключением для медиагрупп

        Args:
            handler: Следующий обработчик
            event: Событие
            data: Данные события

        Returns:
            Результат обработки или None если заблокировано
        """
        try:
            import time

            user = event.from_user
            if not user:
                return await handler(event, data)

            # Пропускаем проверку для админа
            if user.id == settings.ADMIN_ID:
                return await handler(event, data)

            current_time = time.time()
            user_id = user.id

            # Специальная обработка для медиагрупп
            if isinstance(event, Message) and event.media_group_id:
                media_group_id = event.media_group_id

                # Проверяем, обрабатывали ли мы эту медиагруппу недавно
                if media_group_id in self.media_groups:
                    last_time = self.media_groups[media_group_id]
                    if current_time - last_time < 2.0:  # Разрешаем медиагруппу в течение 2 секунд
                        self.media_groups[media_group_id] = current_time
                        return await handler(event, data)

                # Новая медиагруппа
                self.media_groups[media_group_id] = current_time
                self.user_timings[user_id] = current_time

                # Очищаем старые медиагруппы
                cutoff_time = current_time - 60
                self.media_groups = {
                    mid: timestamp
                    for mid, timestamp in self.media_groups.items()
                    if timestamp > cutoff_time
                }

                return await handler(event, data)

            # Обычная проверка для не-медиагрупп
            if user_id in self.user_timings:
                if current_time - self.user_timings[user_id] < self.limit:
                    # Слишком быстро, игнорируем
                    logger.warning(f"Пользователь {user_id} превысил лимит частоты запросов")

                    # Для callback запросов отвечаем, чтобы убрать "часики"
                    if isinstance(event, CallbackQuery):
                        try:
                            await event.answer("⏱ Слишком быстро! Подождите немного.")
                        except:
                            pass

                    return None

            # Обновляем время последнего обращения
            self.user_timings[user_id] = current_time

            # Очищаем старые записи (старше 1 минуты)
            cutoff_time = current_time - 60
            self.user_timings = {
                uid: timestamp
                for uid, timestamp in self.user_timings.items()
                if timestamp > cutoff_time
            }

            return await handler(event, data)

        except Exception as e:
            logger.error(f"Ошибка в ThrottlingMiddleware: {e}")
            return await handler(event, data)

class ErrorHandlingMiddleware(BaseMiddleware):
    """
    Middleware для глобальной обработки ошибок
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        """
        Глобальная обработка ошибок

        Args:
            handler: Следующий обработчик
            event: Событие
            data: Данные события

        Returns:
            Результат обработки
        """
        try:
            return await handler(event, data)

        except Exception as e:
            logger.error(f"Необработанная ошибка в обработчике: {e}", exc_info=True)

            user = event.from_user
            error_text = "❌ Произошла внутренняя ошибка. Попробуйте позже."

            try:
                if isinstance(event, Message):
                    await event.answer(error_text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_text, show_alert=True)

                # Уведомляем админа о критической ошибке
                if user and user.id != settings.ADMIN_ID:
                    error_details = f"""
🚨 <b>Критическая ошибка!</b>

Пользователь: {user.id} (@{user.username or 'нет username'})
Ошибка: <code>{str(e)[:200]}</code>

Требуется проверка системы!
                    """

                    await send_notification_to_admin(data.get('bot'), error_details)

            except Exception as notification_error:
                logger.error(f"Ошибка отправки уведомления об ошибке: {notification_error}")

            return None


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования всех событий
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        """
        Логирование событий

        Args:
            handler: Следующий обработчик
            event: Событие
            data: Данные события

        Returns:
            Результат обработки
        """
        try:
            user = event.from_user

            # Формируем лог-сообщение
            if isinstance(event, Message):
                log_msg = f"Message from {user.id}"
                if event.text:
                    log_msg += f": {event.text[:100]}"
                elif event.photo:
                    log_msg += ": [Photo]"
                elif event.document:
                    log_msg += ": [Document]"
            elif isinstance(event, CallbackQuery):
                log_msg = f"Callback from {user.id}: {event.data}"
            else:
                log_msg = f"Unknown event from {user.id}"

            logger.debug(log_msg)

            # Обрабатываем событие
            result = await handler(event, data)

            return result

        except Exception as e:
            logger.error(f"Ошибка в LoggingMiddleware: {e}")
            return await handler(event, data)