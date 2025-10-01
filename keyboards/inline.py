"""\
Inline клавиатуры для бота
Создание различных inline-кнопок для взаимодействия с пользователем
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

from config import PostType, PaymentMethod, ItemCondition


class MainKeyboards:
    """Основные клавиатуры бота"""

    @staticmethod
    def get_main_menu(user_id: int, admin_id: int) -> InlineKeyboardMarkup:

        """
        Главное меню бота

        Returns:
            Inline клавиатура главного меню
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="📝 Разместить пост",
            callback_data="create_post"
        ))

        builder.add(InlineKeyboardButton(
            text="📋 Мои посты",
            callback_data="my_posts"
        ))

        builder.add(InlineKeyboardButton(
            text="💳 История платежей",
            callback_data="my_payments"
        ))

        # Кнопка админ-панели только для администратора
        if user_id == admin_id:
            builder.add(InlineKeyboardButton(
                text="👑 Админ-панель",
                callback_data="admin_panel_mode"
            ))

        builder.add(InlineKeyboardButton(
            text="ℹ️ Информация",
            callback_data="info"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def get_post_type_menu() -> InlineKeyboardMarkup:
        """
        Меню выбора типа поста

        Returns:
            Inline клавиатура выбора типа поста
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="📝 Обычный пост (200₽)",
            callback_data=f"post_type:{PostType.REGULAR}"
        ))

        builder.add(InlineKeyboardButton(
            text="📌 Закрепленный пост (1000₽)",
            callback_data=f"post_type:{PostType.PINNED}"
        ))

        builder.add(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_main"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def get_payment_method_menu() -> InlineKeyboardMarkup:
        """
        Меню выбора способа оплаты

        Returns:
            Inline клавиатура выбора способа оплаты
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="🏦 СБП (банковская карта)",
            callback_data=f"payment:{PaymentMethod.SBP}"
        ))

        builder.add(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_post_type"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def get_payment_status_menu(payment_id: int) -> InlineKeyboardMarkup:
        """
        Меню проверки статуса платежа

        Args:
            payment_id: ID платежа

        Returns:
            Inline клавиатура проверки платежа
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="🔄 Проверить платеж",
            callback_data=f"check_payment:{payment_id}"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_payment"
        ))

        builder.adjust(1)
        return builder.as_markup()


class PostKeyboards:
    """Клавиатуры для работы с постами"""

    @staticmethod
    def get_item_condition_menu() -> InlineKeyboardMarkup:
        """
        Меню выбора состояния товара

        Returns:
            Inline клавиатура выбора состояния
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="✨ Новое",
            callback_data=f"condition:{ItemCondition.NEW}"
        ))

        builder.add(InlineKeyboardButton(
            text="🔄 Б/у",
            callback_data=f"condition:{ItemCondition.USED}"
        ))

        builder.adjust(2)
        return builder.as_markup()

    @staticmethod
    def get_post_confirmation_menu() -> InlineKeyboardMarkup:
        """
        Меню подтверждения данных поста

        Returns:
            Inline клавиатура подтверждения
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="✅ Опубликовать",
            callback_data="confirm_post"
        ))

        builder.add(InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data="edit_post"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_post"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def get_edit_post_menu() -> InlineKeyboardMarkup:
        """
        Меню редактирования поста

        Returns:
            Inline клавиатура редактирования
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="📸 Изменить фото",
            callback_data="edit_photos"
        ))

        builder.add(InlineKeyboardButton(
            text="📝 Изменить название",
            callback_data="edit_title"
        ))

        builder.add(InlineKeyboardButton(
            text="📄 Изменить описание",
            callback_data="edit_description"
        ))

        builder.add(InlineKeyboardButton(
            text="💰 Изменить цену",
            callback_data="edit_price"
        ))

        builder.add(InlineKeyboardButton(
            text="📞 Изменить контакты",
            callback_data="edit_contact"
        ))

        builder.add(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_confirmation"
        ))

        builder.adjust(2, 1)
        return builder.as_markup()

    @staticmethod
    def get_my_posts_menu(posts: List[Dict]) -> InlineKeyboardMarkup:
        """
        Меню просмотра постов пользователя

        Args:
            posts: Список постов пользователя

        Returns:
            Inline клавиатура с постами
        """
        builder = InlineKeyboardBuilder()

        for post in posts:
            status_emoji = {
                'draft': '📝',
                'published': '✅',
                'archived': '📦'
            }.get(post['status'], '❓')

            builder.add(InlineKeyboardButton(
                text=f"{status_emoji} {post['title'][:30]}...",
                callback_data=f"view_post:{post['post_id']}"
            ))

        if not posts:
            builder.add(InlineKeyboardButton(
                text="❌ У вас нет постов",
                callback_data="no_posts"
            ))

        builder.add(InlineKeyboardButton(
            text="◀️ Главное меню",
            callback_data="back_to_main"
        ))

        builder.adjust(1)
        return builder.as_markup()

class AdminKeyboards:
    """Клавиатуры для администратора"""

    @staticmethod
    def get_admin_menu() -> InlineKeyboardMarkup:
        """
        Главное меню администратора

        Returns:
            Inline клавиатура админ-панели
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="💳 Платежи на проверке",
            callback_data="admin_payments"
        ))

        builder.add(InlineKeyboardButton(
            text="🧾 Управление чеками",
            callback_data="admin_receipts"
        ))

        builder.add(InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="admin_stats"
        ))

        builder.add(InlineKeyboardButton(
            text="👥 Пользователи",
            callback_data="admin_users"
        ))

        builder.add(InlineKeyboardButton(
            text="📢 Рассылка",
            callback_data="admin_broadcast"
        ))

        builder.add(InlineKeyboardButton(
            text="📋 Логи",
            callback_data="admin_logs"
        ))

        builder.add(InlineKeyboardButton(
            text="👤 Режим пользователя",
            callback_data="switch_to_user_mode"
        ))
        builder.add(InlineKeyboardButton(
                text="💾 Бэкапы",
                callback_data="admin_backups"
        ))

        builder.adjust(2, 2, 2)
        return builder.as_markup()

    @staticmethod
    def get_payment_moderation_menu(payment_id: int) -> InlineKeyboardMarkup:
        """
        Меню модерации платежа

        Args:
            payment_id: ID платежа

        Returns:
            Inline клавиатура модерации
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_payment:{payment_id}"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject_payment:{payment_id}"
        ))

        builder.add(InlineKeyboardButton(
            text="👤 Профиль пользователя",
            callback_data=f"user_profile:{payment_id}"
        ))

        builder.add(InlineKeyboardButton(
            text="◀️ Назад к списку",
            callback_data="admin_payments"
        ))

        builder.adjust(2, 1, 1)
        return builder.as_markup()

    @staticmethod
    def get_payments_list_menu(payments: List[Dict]) -> InlineKeyboardMarkup:
        """
        Список платежей на проверке

        Args:
            payments: Список платежей

        Returns:
            Inline клавиатура со списком платежей
        """
        builder = InlineKeyboardBuilder()

        for payment in payments:
            method_emoji = "🏦" if payment['method'] == PaymentMethod.SBP else "₿"
            builder.add(InlineKeyboardButton(
                text=f"{method_emoji} {payment['amount']}₽ - {payment['first_name'] or 'Без имени'}",
                callback_data=f"moderate_payment:{payment['payment_id']}"
            ))

        if not payments:
            builder.add(InlineKeyboardButton(
                text="✅ Нет платежей на проверке",
                callback_data="no_pending_payments"
            ))

        builder.add(InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="admin_payments"
        ))

        builder.add(InlineKeyboardButton(
            text="◀️ Админ-панель",
            callback_data="admin_menu"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def get_broadcast_confirmation_menu() -> InlineKeyboardMarkup:
        """
        Меню подтверждения рассылки

        Returns:
            Inline клавиатура подтверждения рассылки
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="✅ Отправить всем",
            callback_data="confirm_broadcast"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_broadcast"
        ))

        builder.adjust(1)
        return builder.as_markup()


class NavigationKeyboards:
    """Навигационные клавиатуры"""

    @staticmethod
    def get_back_to_main_menu() -> InlineKeyboardMarkup:
        """
        Кнопка возврата в главное меню

        Returns:
            Inline клавиатура с кнопкой "Назад"
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="◀️ Главное меню",
            callback_data="back_to_main"
        ))

        return builder.as_markup()

    @staticmethod
    def get_close_menu() -> InlineKeyboardMarkup:
        """
        Кнопка закрытия меню

        Returns:
            Inline клавиатура с кнопкой "Закрыть"
        """
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data="close_menu"
        ))

        return builder.as_markup()

    @staticmethod
    def get_pagination_keyboard(current_page: int, total_pages: int,
                               callback_prefix: str) -> InlineKeyboardMarkup:
        """
        Клавиатура пагинации

        Args:
            current_page: Текущая страница
            total_pages: Общее количество страниц
            callback_prefix: Префикс для callback_data

        Returns:
            Inline клавиатура пагинации
        """
        builder = InlineKeyboardBuilder()

        # Кнопки навигации
        buttons = []

        if current_page > 1:
            buttons.append(InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{callback_prefix}:{current_page - 1}"
            ))

        buttons.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="current_page"
        ))

        if current_page < total_pages:
            buttons.append(InlineKeyboardButton(
                text="➡️",
                callback_data=f"{callback_prefix}:{current_page + 1}"
            ))

        for button in buttons:
            builder.add(button)

        builder.adjust(len(buttons))
        return builder.as_markup()


# Вспомогательные функции для работы с клавиатурами

def add_back_button(builder: InlineKeyboardBuilder,
                   callback_data: str = "back_to_main") -> InlineKeyboardBuilder:
    """
    Добавление кнопки "Назад" к существующей клавиатуре

    Args:
        builder: Строитель клавиатуры
        callback_data: Callback для кнопки назад

    Returns:
        Обновленный строитель
    """
    builder.add(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=callback_data
    ))
    return builder


def create_yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры Да/Нет

    Args:
        yes_callback: Callback для кнопки "Да"
        no_callback: Callback для кнопки "Нет"

    Returns:
        Inline клавиатура Да/Нет
    """
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(
        text="✅ Да",
        callback_data=yes_callback
    ))

    builder.add(InlineKeyboardButton(
        text="❌ Нет",
        callback_data=no_callback
    ))

    builder.adjust(2)
    return builder.as_markup()

