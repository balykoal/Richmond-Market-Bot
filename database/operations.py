"""
Операции с базой данных
Асинхронные функции для работы с таблицами
"""

import json
import logging
from typing import Optional, List, Dict, Any

from config import PaymentStatus, PostStatus
from .connector import get_connection

logger = logging.getLogger(__name__)


class DatabaseOperations:
    """Базовый класс для операций с БД"""

    @staticmethod
    def dict_from_record(record) -> Optional[Dict]:
        """Конвертация записи в словарь"""
        return dict(record) if record else None


class UserOperations(DatabaseOperations):
    """Операции с пользователями"""

    @staticmethod
    async def update_offer_accepted(user_id: int) -> bool:
        """
        Отметить, что пользователь принял публичную оферту

        Args:
            user_id: ID пользователя

        Returns:
            True если обновлено успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE users SET offer_accepted = TRUE, offer_accepted_at = CURRENT_TIMESTAMP WHERE user_id = $1",
                    user_id
                )
                logger.info(f"Пользователь {user_id} принял оферту")
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления принятия оферты для {user_id}: {e}")
            return False

    @staticmethod
    async def has_accepted_offer(user_id: int) -> bool:
        """
        Проверить, принял ли пользователь публичную оферту

        Args:
            user_id: ID пользователя

        Returns:
            True если оферта принята
        """
        try:
            async with get_connection() as conn:
                result = await conn.fetchval(
                    "SELECT offer_accepted FROM users WHERE user_id = $1",
                    user_id
                )
                return bool(result) if result is not None else False
        except Exception as e:
            logger.error(f"Ошибка проверки принятия оферты для {user_id}: {e}")
            return False

    @staticmethod
    async def create_user(user_id: int, username: str = None,
                         first_name: str = None, last_name: str = None) -> bool:
        """
        Создание нового пользователя

        Args:
            user_id: ID пользователя Telegram
            username: Имя пользователя
            first_name: Имя
            last_name: Фамилия

        Returns:
            True если пользователь создан успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name
                    """,
                    user_id, username, first_name, last_name
                )
                logger.info(f"Пользователь {user_id} создан/обновлен")
                return True
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")
            return False

    @staticmethod
    async def get_user(user_id: int) -> Optional[Dict]:
        """
        Получение пользователя по ID

        Args:
            user_id: ID пользователя

        Returns:
            Данные пользователя или None
        """
        async with get_connection() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            return UserOperations.dict_from_record(record)

    @staticmethod
    async def update_phone(user_id: int, phone: str) -> bool:
        """
        Обновление номера телефона пользователя

        Args:
            user_id: ID пользователя
            phone: Номер телефона

        Returns:
            True если обновлено успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE users SET phone = $1 WHERE user_id = $2",
                    phone, user_id
                )
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления телефона пользователя {user_id}: {e}")
            return False

    @staticmethod
    async def get_all_users() -> List[Dict]:
        """
        Получение всех пользователей

        Returns:
            Список всех пользователей
        """
        async with get_connection() as conn:
            records = await conn.fetch("SELECT * FROM users ORDER BY reg_date DESC")
            return [dict(record) for record in records]

    @staticmethod
    async def increment_post_count(user_id: int) -> bool:
        """
        Увеличение счетчика постов пользователя

        Args:
            user_id: ID пользователя

        Returns:
            True если обновлено успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE users SET post_count = post_count + 1 WHERE user_id = $1",
                    user_id
                )
                return True
        except Exception as e:
            logger.error(f"Ошибка увеличения счетчика постов пользователя {user_id}: {e}")
            return False

class PostOperations(DatabaseOperations):
    """Операции с постами"""

    @staticmethod
    async def create_post(user_id: int, photos: List[str], title: str,
                         condition: str, description: str, price: float,
                         contact_info: str, post_type: str) -> Optional[int]:
        """
        Создание нового поста

        Args:
            user_id: ID пользователя
            photos: Список фотографий
            title: Название товара
            condition: Состояние товара
            description: Описание
            price: Цена
            contact_info: Контактная информация
            post_type: Тип поста

        Returns:
            ID созданного поста или None
        """
        try:
            async with get_connection() as conn:
                record = await conn.fetchrow(
                    """
                    INSERT INTO posts (user_id, photos, title, condition, description, 
                                     price, contact_info, post_type, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING post_id
                    """,
                    user_id, photos, title, condition, description,
                    price, contact_info, post_type, PostStatus.DRAFT
                )
                post_id = record['post_id'] if record else None
                logger.info(f"Пост {post_id} создан для пользователя {user_id}")
                return post_id
        except Exception as e:
            logger.error(f"Ошибка создания поста: {e}")
            return None

    @staticmethod
    async def get_post(post_id: int) -> Optional[Dict]:
        """
        Получение поста по ID

        Args:
            post_id: ID поста

        Returns:
            Данные поста или None
        """
        async with get_connection() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM posts WHERE post_id = $1", post_id
            )
            return PostOperations.dict_from_record(record)

    @staticmethod
    async def publish_post(post_id: int, message_id: int) -> bool:
        """
        Публикация поста

        Args:
            post_id: ID поста
            message_id: ID сообщения в канале

        Returns:
            True если опубликовано успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE posts SET status = $1, message_id = $2, published_at = CURRENT_TIMESTAMP
                    WHERE post_id = $3
                    """,
                    PostStatus.PUBLISHED, message_id, post_id
                )
                logger.info(f"Пост {post_id} опубликован (message_id: {message_id})")
                return True
        except Exception as e:
            logger.error(f"Ошибка публикации поста {post_id}: {e}")
            return False

    @staticmethod
    async def get_user_posts(user_id: int) -> List[Dict]:
        """
        Получение всех постов пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Список постов пользователя
        """
        async with get_connection() as conn:
            records = await conn.fetch(
                "SELECT * FROM posts WHERE user_id = $1 ORDER BY created_at DESC",
                user_id
            )
            return [dict(record) for record in records]

    @staticmethod
    async def get_posts_by_status(status: str) -> List[Dict]:
        """
        Получение постов по статусу

        Args:
            status: Статус поста

        Returns:
            Список постов с указанным статусом
        """
        async with get_connection() as conn:
            records = await conn.fetch(
                "SELECT * FROM posts WHERE status = $1 ORDER BY created_at DESC",
                status
            )
            return [dict(record) for record in records]


class PaymentOperations(DatabaseOperations):
    """Операции с платежами"""

    @staticmethod
    async def create_payment(user_id: int, amount: float, method: str,
                           post_id: int = None, currency: str = "RUB",
                           transaction_data: Dict = None) -> Optional[int]:
        """
        Создание нового платежа

        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            method: Способ оплаты
            post_id: ID поста (опционально)
            currency: Валюта
            transaction_data: Дополнительные данные

        Returns:
            ID созданного платежа или None
        """
        try:
            async with get_connection() as conn:
                record = await conn.fetchrow(
                    """
                    INSERT INTO payments (user_id, post_id, amount, currency, method, 
                                        transaction_data, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING payment_id
                    """,
                    user_id, post_id, amount, currency, method,
                    transaction_data, PaymentStatus.PENDING
                )
                payment_id = record['payment_id'] if record else None
                logger.info(f"Платеж {payment_id} создан для пользователя {user_id}")
                return payment_id
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return None

    @staticmethod
    async def get_payment(payment_id: int) -> Optional[Dict]:
        """
        Получение платежа по ID

        Args:
            payment_id: ID платежа

        Returns:
            Данные платежа или None
        """
        async with get_connection() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM payments WHERE payment_id = $1", payment_id
            )
            return PaymentOperations.dict_from_record(record)

    @staticmethod
    async def confirm_payment(payment_id: int, admin_id: int) -> bool:
        """
        Подтверждение платежа администратором

        Args:
            payment_id: ID платежа
            admin_id: ID администратора

        Returns:
            True если подтвержден успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE payments SET status = $1, confirmed_at = CURRENT_TIMESTAMP,
                                      confirmed_by = $2
                    WHERE payment_id = $3
                    """,
                    PaymentStatus.CONFIRMED, admin_id, payment_id
                )
                logger.info(f"Платеж {payment_id} подтвержден админом {admin_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка подтверждения платежа {payment_id}: {e}")
            return False

    @staticmethod
    async def reject_payment(payment_id: int, admin_id: int, reason: str = None) -> bool:
        """
        Отклонение платежа администратором

        Args:
            payment_id: ID платежа
            admin_id: ID администратора
            reason: Причина отклонения

        Returns:
            True если отклонен успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE payments SET status = $1, confirmed_by = $2, rejection_reason = $3
                    WHERE payment_id = $4
                    """,
                    PaymentStatus.REJECTED, admin_id, reason, payment_id
                )
                logger.info(f"Платеж {payment_id} отклонен админом {admin_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка отклонения платежа {payment_id}: {e}")
            return False

    @staticmethod
    async def get_pending_payments() -> List[Dict]:
        """
        Получение платежей на проверке

        Returns:
            Список платежей со статусом checking
        """
        try:
            async with get_connection() as conn:
                records = await conn.fetch(
                    """
                    SELECT p.*, u.username, u.first_name, u.last_name 
                    FROM payments p
                    LEFT JOIN users u ON p.user_id = u.user_id
                    WHERE p.status = $1 
                    ORDER BY p.created_at ASC
                    """,
                    PaymentStatus.CHECKING
                )
                result = [dict(record) for record in records]
                logger.info(f"Найдено платежей на проверке: {len(result)}")
                return result
        except Exception as e:
            logger.error(f"Ошибка получения платежей на проверке: {e}")
            return []

    @staticmethod
    async def update_payment_status(payment_id: int, status: str) -> bool:
        """
        Обновление статуса платежа

        Args:
            payment_id: ID платежа
            status: Новый статус

        Returns:
            True если обновлен успешно
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE payments SET status = $1 WHERE payment_id = $2",
                    status, payment_id
                )
                logger.info(f"Статус платежа {payment_id} изменен на {status}")
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа {payment_id}: {e}")
            return False

    @staticmethod
    async def get_user_payments(user_id: int) -> List[Dict]:
        """
        Получение всех платежей пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Список платежей пользователя
        """
        async with get_connection() as conn:
            records = await conn.fetch(
                "SELECT * FROM payments WHERE user_id = $1 ORDER BY created_at DESC",
                user_id
            )
            return [dict(record) for record in records]


class AdminOperations(DatabaseOperations):
    """Операции администратора"""

    @staticmethod
    async def log_admin_action(admin_id: int, action: str, details: Dict = None,
                               target_user_id: int = None, target_payment_id: int = None) -> bool:
        """
        Логирование действия администратора

        Args:
            admin_id: ID администратора
            action: Выполненное действие
            details: Детали действия (должны быть JSON-сериализуемыми)
            target_user_id: ID пользователя (если применимо)
            target_payment_id: ID платежа (если применимо)

        Returns:
            True если залогировано успешно
        """
        try:
            async with get_connection() as conn:
                # Сериализуем details в JSON строку
                details_json = json.dumps(details) if details else None

                await conn.execute(
                    """
                    INSERT INTO admin_logs (admin_id, action, details, target_user_id, target_payment_id)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    admin_id, action, details_json, target_user_id, target_payment_id
                )
                return True
        except Exception as e:
            logger.error(f"Ошибка логирования действия админа {admin_id}: {e}")
            return False

    @staticmethod
    async def get_admin_logs(admin_id: int = None, limit: int = 100) -> List[Dict]:
        """
        Получение логов администратора

        Args:
            admin_id: ID администратора (если нужен конкретный)
            limit: Максимальное количество записей

        Returns:
            Список логов
        """
        async with get_connection() as conn:
            if admin_id:
                records = await conn.fetch(
                    """
                    SELECT * FROM admin_logs
                    WHERE admin_id = $1
                    ORDER BY timestamp DESC
                    LIMIT $2
                    """,
                    admin_id, limit
                )
            else:
                records = await conn.fetch(
                    "SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT $1",
                    limit
                )

            logs: list[dict[str | Any, dict[str, str] | Any]] = []
            for record in records:
                log_dict = dict(record)
                # Преобразуем details из JSON строки обратно в словарь
                if log_dict.get('details') and isinstance(log_dict['details'], str):
                    try:
                        log_dict['details'] = json.loads(log_dict['details'])
                    except json.JSONDecodeError:
                        log_dict['details'] = {"error": "Invalid JSON format"}
                logs.append(log_dict)
            return logs


    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        """
        Получение статистики системы

        Returns:
            Словарь со статистикой
        """
        async with get_connection() as conn:
            # Общая статистика пользователей
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            new_users_today = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE DATE(reg_date) = CURRENT_DATE"
            )

            # Статистика постов
            total_posts = await conn.fetchval("SELECT COUNT(*) FROM posts")
            published_posts = await conn.fetchval(
                "SELECT COUNT(*) FROM posts WHERE status = $1", PostStatus.PUBLISHED
            )
            posts_today = await conn.fetchval(
                "SELECT COUNT(*) FROM posts WHERE DATE(created_at) = CURRENT_DATE"
            )

            # Статистика платежей
            total_payments = await conn.fetchval("SELECT COUNT(*) FROM payments")
            confirmed_payments = await conn.fetchval(
                "SELECT COUNT(*) FROM payments WHERE status = $1", PaymentStatus.CONFIRMED
            )
            pending_payments = await conn.fetchval(
                "SELECT COUNT(*) FROM payments WHERE status = $1", PaymentStatus.CHECKING
            )
            total_revenue = await conn.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = $1",
                PaymentStatus.CONFIRMED
            )

            return {
                'users': {
                    'total': total_users,
                    'new_today': new_users_today
                },
                'posts': {
                    'total': total_posts,
                    'published': published_posts,
                    'today': posts_today
                },
                'payments': {
                    'total': total_payments,
                    'confirmed': confirmed_payments,
                    'pending': pending_payments,
                    'revenue': float(total_revenue) if total_revenue else 0.0
                }
            }


class ReceiptOperations(DatabaseOperations):
    """Операции с чеками"""

    @staticmethod
    async def create_receipt(payment_id: int, user_id: int, admin_id: int,
                             file_id: str, file_type: str, file_name: str) -> Optional[int]:
        """
        Создание записи о чеке

        Args:
            payment_id: ID платежа
            user_id: ID пользователя
            admin_id: ID администратора
            file_id: ID файла в Telegram
            file_type: Тип файла
            file_name: Имя файла

        Returns:
            ID созданной записи
        """
        try:
            async with get_connection() as conn:
                record = await conn.fetchrow(
                    """
                    INSERT INTO receipts (payment_id, user_id, admin_id, file_id, file_type, file_name)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING receipt_id
                    """,
                    payment_id, user_id, admin_id, file_id, file_type, file_name
                )
                receipt_id = record['receipt_id'] if record else None
                logger.info(f"Создан чек {receipt_id} для платежа {payment_id}")
                return receipt_id
        except Exception as e:
            logger.error(f"Ошибка создания чека: {e}")
            return None

    @staticmethod
    async def payment_has_receipt(payment_id: int) -> bool:
        """
        Проверка наличия чека для платежа

        Args:
            payment_id: ID платежа

        Returns:
            True если чек существует
        """
        async with get_connection() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM receipts WHERE payment_id = $1",
                payment_id
            )
            return count > 0

    @staticmethod
    async def get_payments_without_receipts() -> List[Dict]:
        """
        Получение подтвержденных платежей без чеков

        Returns:
            Список платежей без чеков
        """
        async with get_connection() as conn:
            records = await conn.fetch(
                """
                SELECT p.payment_id, p.user_id, p.amount, p.created_at, p.confirmed_at,
                       u.username, u.first_name, u.last_name
                FROM payments p
                LEFT JOIN receipts r ON p.payment_id = r.payment_id
                LEFT JOIN users u ON p.user_id = u.user_id
                WHERE p.status = $1 AND r.receipt_id IS NULL
                ORDER BY p.confirmed_at DESC
                LIMIT 30
                """,
                PaymentStatus.CONFIRMED
            )
            return [dict(record) for record in records]

    @staticmethod
    async def get_payments_with_receipts() -> List[Dict]:
        """
        Получение платежей с чеками

        Returns:
            Список платежей с чеками
        """
        async with get_connection() as conn:
            records = await conn.fetch(
                """
                SELECT p.payment_id, p.user_id, p.amount, p.created_at, p.confirmed_at,
                       u.username, u.first_name, u.last_name,
                       r.receipt_id, r.file_type, r.file_name, r.sent_at
                FROM payments p
                INNER JOIN receipts r ON p.payment_id = r.payment_id
                LEFT JOIN users u ON p.user_id = u.user_id
                WHERE p.status = $1
                ORDER BY r.sent_at DESC
                LIMIT 30
                """,
                PaymentStatus.CONFIRMED
            )
            return [dict(record) for record in records]

    @staticmethod
    async def get_receipt_stats() -> Dict[str, int]:
        """
        Получение статистики по чекам

        Returns:
            Статистика
        """
        async with get_connection() as conn:
            # Общее количество подтвержденных платежей
            total_payments = await conn.fetchval(
                "SELECT COUNT(*) FROM payments WHERE status = $1",
                PaymentStatus.CONFIRMED
            )

            # Количество отправленных чеков
            sent_receipts = await conn.fetchval(
                "SELECT COUNT(*) FROM receipts"
            )

            # Чеки отправленные сегодня
            today_receipts = await conn.fetchval(
                "SELECT COUNT(*) FROM receipts WHERE DATE(sent_at) = CURRENT_DATE"
            )

            return {
                'total_payments': total_payments or 0,
                'sent_receipts': sent_receipts or 0,
                'pending_receipts': (total_payments or 0) - (sent_receipts or 0),
                'today_receipts': today_receipts or 0
            }
