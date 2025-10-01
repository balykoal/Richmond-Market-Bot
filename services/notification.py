"""
Сервис уведомлений
Автоматическая проверка платежей и отправка уведомлений
"""

import asyncio
import logging
from typing import List, Dict
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import PaymentOperations, UserOperations
from utils.helpers import send_notification_to_admin, format_price, format_datetime
from config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.is_running = False

    async def start_payment_checker(self) -> None:
        """
        Запуск автоматической проверки платежей
        Проверяет статус платежей каждые 5 минут
        """
        self.is_running = True
        logger.info("Сервис проверки платежей запущен")

        while self.is_running:
            try:
                await self._check_pending_payments()
                await asyncio.sleep(settings.PAYMENT_CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Ошибка в сервисе проверки платежей: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке

    def stop_payment_checker(self) -> None:
        """Остановка сервиса проверки платежей"""
        self.is_running = False
        logger.info("Сервис проверки платежей остановлен")

    async def _check_pending_payments(self) -> None:
        """
        Проверка платежей в статусе ожидания
        Уведомляет админа о платежах, которые нужно проверить
        """
        try:
            # Получаем платежи на проверке
            pending_payments = await PaymentOperations.get_pending_payments()

            if pending_payments:
                logger.info(f"Найдено {len(pending_payments)} платежей на проверке")

                # Уведомляем админа если есть необработанные платежи
                text = f"""
🔔 <b>Напоминание о платежах</b>

На проверке {len(pending_payments)} платежей:

"""

                for payment in pending_payments[:5]:  # Показываем первые 5
                    method_text = "СБП" if payment['method'] == 'sbp' else "Крипта"
                    user_name = payment.get('first_name', 'Без имени')

                    text += f"""
💳 №{payment['payment_id']} - {format_price(payment['amount'])} ₽ ({method_text})
👤 {user_name} | {format_datetime(payment['created_at'])}
"""

                if len(pending_payments) > 5:
                    text += f"\n... и еще {len(pending_payments) - 5} платежей"

                text += "\n\nИспользуйте /admin для проверки платежей."

                await send_notification_to_admin(self.bot, text)

        except Exception as e:
            logger.error(f"Ошибка проверки pending платежей: {e}")

    async def notify_payment_confirmed(self, payment_id: int) -> bool:
        """
        Уведомление пользователя о подтверждении платежа (старый метод для совместимости)

        Args:
            payment_id: ID платежа

        Returns:
            True если уведомление отправлено успешно
        """
        return await self.notify_payment_confirmed_with_post_creation(payment_id)

    async def notify_payment_confirmed_with_post_creation(self, payment_id: int) -> bool:
        """
        Уведомление пользователя о подтверждении платежа с переходом к созданию поста

        Args:
            payment_id: ID платежа

        Returns:
            True если уведомление отправлено успешно
        """
        try:
            # Получаем данные платежа
            payment = await PaymentOperations.get_payment(payment_id)
            if not payment:
                logger.error(f"Платеж {payment_id} не найден")
                return False

            # Получаем данные пользователя
            user = await UserOperations.get_user(payment['user_id'])
            if not user:
                logger.error(f"Пользователь {payment['user_id']} не найден")
                return False

            # Определяем тип поста по сумме
            post_type = 'regular'
            if payment['amount'] == settings.PINNED_POST_PRICE:
                post_type = 'pinned'
            elif payment['amount'] == settings.REGULAR_POST_PRICE:
                post_type = 'regular'

            # Формируем текст уведомления
            method_text = "СБП" if payment['method'] == 'sbp' else "криптовалютой"
            post_type_name = "Закрепленный" if post_type == 'pinned' else "Обычный"

            text = f"""
✅ <b>Платеж подтвержден!</b>

Ваш платеж №{payment_id} на сумму {format_price(payment['amount'])} ₽ ({method_text}) успешно подтвержден администратором.

Тип поста: <b>{post_type_name}</b>

Теперь приступим к созданию поста! 📝

📸 <b>Шаг 1: Загрузите фотографии</b>

Отправьте от {settings.MIN_PHOTOS} до {settings.MAX_PHOTOS} фотографий вашего товара.

💡 <b>Советы для хороших фото:</b>
• Делайте фото при хорошем освещении
• Показывайте товар с разных ракурсов  
• Включите фото дефектов (если есть)
• Фотографии должны быть четкими

<b>Нажмите кнопку ниже для продолжения создания поста</b>
"""

            # Создаем inline кнопку для продолжения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="📝 Создать пост",
                    callback_data=f"continue_post:{payment_id}"
                )
            ]])

            # Отправляем уведомление пользователю
            await self.bot.send_message(
                chat_id=payment['user_id'],
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            logger.info(f"Пользователь {payment['user_id']} уведомлен о подтверждении платежа {payment_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка уведомления о подтверждении платежа {payment_id}: {e}")
            return False

    async def notify_payment_rejected(self, payment_id: int, reason: str = None) -> bool:
        """
        Уведомление пользователя об отклонении платежа

        Args:
            payment_id: ID платежа
            reason: Причина отклонения

        Returns:
            True если уведомление отправлено успешно
        """
        try:
            # Получаем данные платежа
            payment = await PaymentOperations.get_payment(payment_id)
            if not payment:
                return False

            # Формируем текст уведомления
            method_text = "СБП" if payment['method'] == 'sbp' else "криптовалютой"
            reason_text = f"\n\n<b>Причина:</b> {reason}" if reason else ""

            text = f"""
❌ <b>Платеж отклонен</b>

К сожалению, ваш платеж №{payment_id} на сумму {format_price(payment['amount'])} ₽ ({method_text}) был отклонен администратором.{reason_text}

🤝 <b>Что делать?</b>
Пожалуйста, свяжитесь с поддержкой для выяснения деталей: @balykoal

Вы можете создать новый платеж, используя команду /start
"""

            # Отправляем уведомление пользователю
            await self.bot.send_message(
                chat_id=payment['user_id'],
                text=text,
                parse_mode="HTML"
            )

            logger.info(f"Пользователь {payment['user_id']} уведомлен об отклонении платежа {payment_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка уведомления об отклонении платежа {payment_id}: {e}")
            return False

    async def notify_post_published(self, user_id: int, post_id: int, message_id: int) -> bool:
        """
        Уведомление пользователя о публикации поста

        Args:
            user_id: ID пользователя
            post_id: ID поста
            message_id: ID сообщения в канале

        Returns:
            True если уведомление отправлено успешно
        """
        try:
            text = f"""
🎉 <b>Ваш пост опубликован!</b>

✅ Пост №{post_id} успешно размещен в канале @richmondmarket

🔗 <b>Прямая ссылка:</b>
https://t.me/rc_exchng/{message_id}

📊 <b>Что дальше?</b>
• Ваш пост увидят все подписчики канала
• Заинтересованные покупатели свяжутся с вами
• Следите за входящими сообщениями!

Желаем успешной продажи! 💰
"""

            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            logger.info(f"Пользователь {user_id} уведомлен о публикации поста {post_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка уведомления о публикации поста {post_id}: {e}")
            return False

    async def broadcast_message(self, message_text: str, user_ids: List[int] = None) -> Dict[str, int]:
        """
        Массовая рассылка сообщений пользователям

        Args:
            message_text: Текст сообщения для рассылки
            user_ids: Список ID пользователей (если None - всем)

        Returns:
            Статистика рассылки
        """
        try:
            # Если не указаны пользователи, получаем всех
            if user_ids is None:
                all_users = await UserOperations.get_all_users()
                user_ids = [user['user_id'] for user in all_users]

            stats = {
                'total': len(user_ids),
                'sent': 0,
                'failed': 0,
                'blocked': 0
            }

            logger.info(f"Начинаем рассылку для {len(user_ids)} пользователей")

            for user_id in user_ids:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=message_text,
                        parse_mode="HTML"
                    )

                    stats['sent'] += 1

                    # Небольшая задержка чтобы не превысить лимиты API
                    await asyncio.sleep(0.05)  # 50ms между сообщениями

                except Exception as e:
                    error_msg = str(e)

                    if "blocked by the user" in error_msg or "chat not found" in error_msg:
                        stats['blocked'] += 1
                        logger.debug(f"Пользователь {user_id} заблокировал бота")
                    else:
                        stats['failed'] += 1
                        logger.warning(f"Ошибка отправки пользователю {user_id}: {e}")

            logger.info(
                f"Рассылка завершена. Отправлено: {stats['sent']}, Ошибок: {stats['failed']}, Заблокировано: {stats['blocked']}")

            # Уведомляем админа о результатах
            report = f"""
📢 <b>Рассылка завершена</b>

📊 <b>Статистика:</b>
• Всего получателей: {stats['total']}
• Доставлено: {stats['sent']}
• Заблокировали бота: {stats['blocked']}
• Ошибки доставки: {stats['failed']}

✅ <b>Успешность:</b> {round(stats['sent'] / stats['total'] * 100, 1)}%
"""

            await send_notification_to_admin(self.bot, report)

            return stats

        except Exception as e:
            logger.error(f"Ошибка массовой рассылки: {e}")
            return {'total': 0, 'sent': 0, 'failed': 0, 'blocked': 0}

    async def send_admin_notification(self, title: str, message: str, urgent: bool = False) -> bool:
        """
        Отправка уведомления администратору

        Args:
            title: Заголовок уведомления
            message: Текст сообщения
            urgent: Срочное уведомление

        Returns:
            True если отправлено успешно
        """
        try:
            prefix = "🚨" if urgent else "📢"

            text = f"""
{prefix} <b>{title}</b>

{message}

<i>Время: {format_datetime(None)}</i>
"""

            await self.bot.send_message(
                chat_id=settings.ADMIN_ID,
                text=text,
                parse_mode="HTML"
            )

            return True

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")
            return False

    async def notify_admin_new_payment(self, payment_id: int) -> bool:
        """
        Уведомление админа о новом платеже с кнопкой перехода к модерации

        Args:
            payment_id: ID платежа

        Returns:
            True если уведомление отправлено успешно
        """
        try:
            from utils.helpers import format_price, format_user_info
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            # Получаем данные платежа
            payment = await PaymentOperations.get_payment(payment_id)
            if not payment:
                return False

            user = await UserOperations.get_user(payment['user_id'])
            if not user:
                return False

            method_text = "🏦 СБП"
            user_info = format_user_info(user)

            text = f"""
    💳 <b>Новый платеж на проверке</b>

    Платеж №{payment_id}
    Пользователь: {user_info}
    Сумма: {format_price(payment['amount'])} ₽
    Способ: {method_text}
    """

            # Создаем кнопку перехода к модерации
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔍 Проверить платеж",
                    callback_data=f"moderate_payment:{payment_id}"
                )]
            ])

            await self.bot.send_message(
                chat_id=settings.ADMIN_ID,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            logger.info(f"Админ уведомлен о новом платеже {payment_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка уведомления админа о платеже {payment_id}: {e}")
            return False

    async def notify_new_user(self, user_id: int) -> bool:
        """
        Уведомление о новом пользователе

        Args:
            user_id: ID нового пользователя

        Returns:
            True если уведомление отправлено
        """
        try:
            user = await UserOperations.get_user(user_id)
            if not user:
                return False

            from utils.helpers import format_user_info

            text = f"""
👋 <b>Новый пользователь</b>

Зарегистрировался: {format_user_info(user)}
Время: {format_datetime(user.get('reg_date'))}

Всего пользователей в боте увеличилось!
"""

            return await self.send_admin_notification("Новый пользователь", text.strip())

        except Exception as e:
            logger.error(f"Ошибка уведомления о новом пользователе {user_id}: {e}")
            return False

    async def notify_system_error(self, error: Exception, context: str = None) -> bool:
        """
        Уведомление о системной ошибке

        Args:
            error: Объект исключения
            context: Контекст ошибки

        Returns:
            True если уведомление отправлено
        """
        try:
            context_text = f" в {context}" if context else ""

            text = f"""
⚠️ <b>Системная ошибка</b>

Произошла ошибка{context_text}:

<code>{str(error)}</code>

Требуется проверка системы!
"""

            return await self.send_admin_notification("Системная ошибка", text, urgent=True)

        except Exception as e:
            logger.error(f"Ошибка уведомления о системной ошибке: {e}")
            return False