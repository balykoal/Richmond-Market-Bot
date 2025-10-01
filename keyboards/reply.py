"""
Reply клавиатуры для бота
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


class ReplyKeyboards:
    """Reply клавиатуры"""

    @staticmethod
    def get_start_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
        """
        Начальная клавиатура

        Args:
            is_admin: Является ли пользователь админом

        Returns:
            Reply клавиатура
        """
        builder = ReplyKeyboardBuilder()

        if is_admin:
            builder.add(KeyboardButton(text="👑 Админ-панель"))
        else:
            builder.add(KeyboardButton(text="🚀 Начать работу"))

        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)