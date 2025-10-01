"""
Валидаторы для проверки данных пользователя
Проверка корректности введенных данных
"""

import re
from typing import List, Optional, Tuple
from config import settings


class ValidationResult:
    """Результат валидации"""

    def __init__(self, is_valid: bool, error_message: str = None):
        self.is_valid = is_valid
        self.error_message = error_message


class DataValidators:
    """Класс для валидации различных типов данных"""

    @staticmethod
    def validate_photos_count(photos: List) -> ValidationResult:
        """
        Валидация количества фотографий

        Args:
            photos: Список фотографий

        Returns:
            Результат валидации
        """
        if not photos:
            return ValidationResult(False, "Необходимо загрузить хотя бы одну фотографию")

        if len(photos) < settings.MIN_PHOTOS:
            return ValidationResult(
                False,
                f"Минимальное количество фотографий: {settings.MIN_PHOTOS}"
            )

        if len(photos) > settings.MAX_PHOTOS:
            return ValidationResult(
                False,
                f"Максимальное количество фотографий: {settings.MAX_PHOTOS}"
            )

        return ValidationResult(True)

    @staticmethod
    def validate_title(title: str) -> ValidationResult:
        """
        Валидация названия товара

        Args:
            title: Название товара

        Returns:
            Результат валидации
        """
        if not title or not title.strip():
            return ValidationResult(False, "Название товара не может быть пустым")

        title = title.strip()

        if len(title) < 5:
            return ValidationResult(False, "Название товара должно содержать минимум 5 символов")

        if len(title) > 100:
            return ValidationResult(False, "Название товара должно содержать максимум 100 символов")

        # Проверка на недопустимые символы
        if re.search(r'[<>"\']', title):
            return ValidationResult(False, "Название не должно содержать символы < > \" '")

        return ValidationResult(True)

    @staticmethod
    def validate_description(description: str) -> ValidationResult:
        """
        Валидация описания товара

        Args:
            description: Описание товара

        Returns:
            Результат валидации
        """
        if not description or not description.strip():
            return ValidationResult(False, "Описание товара не может быть пустым")

        description = description.strip()

        if len(description) < 20:
            return ValidationResult(False, "Описание должно содержать минимум 20 символов")

        if len(description) > 1000:
            return ValidationResult(False, "Описание должно содержать максимум 1000 символов")

        return ValidationResult(True)

    @staticmethod
    def validate_price(price_text: str) -> Tuple[ValidationResult, Optional[float]]:
        """
        Валидация цены товара

        Args:
            price_text: Текст с ценой

        Returns:
            Кортеж (результат валидации, цена в float)
        """
        if not price_text or not price_text.strip():
            return ValidationResult(False, "Цена не может быть пустой"), None

        # Очищаем от лишних символов и пробелов
        price_text = re.sub(r'[^\d.,]', '', price_text.strip())
        price_text = price_text.replace(',', '.')

        try:
            price = float(price_text)
        except ValueError:
            return ValidationResult(False, "Неверный формат цены. Используйте только цифры"), None

        if price <= 0:
            return ValidationResult(False, "Цена должна быть больше 0"), None

        if price > 10000000:  # 10 миллионов
            return ValidationResult(False, "Цена слишком большая"), None

        # Округляем до 2 знаков после запятой
        price = round(price, 2)

        return ValidationResult(True), price

    @staticmethod
    def validate_contact_info(contact: str) -> ValidationResult:
        """
        Валидация контактной информации

        Args:
            contact: Контактная информация

        Returns:
            Результат валидации
        """
        if not contact or not contact.strip():
            return ValidationResult(False, "Контактная информация не может быть пустой")

        contact = contact.strip()

        if len(contact) < 5:
            return ValidationResult(False, "Контактная информация должна содержать минимум 5 символов")

        if len(contact) > 200:
            return ValidationResult(False, "Контактная информация должна содержать максимум 200 символов")

        # Проверяем наличие хотя бы одного способа связи
        has_phone = bool(re.search(r'[\+\d\(\)\-\s]{10,}', contact))
        has_username = bool(re.search(r'@\w+', contact))
        has_email = bool(re.search(r'\S+@\S+\.\S+', contact))

        if not (has_phone or has_username or has_email):
            return ValidationResult(
                False,
                "Укажите способ связи: номер телефона, username Telegram (@username) или email"
            )

        return ValidationResult(True)

    @staticmethod
    def validate_phone_number(phone: str) -> ValidationResult:
        """
        Валидация номера телефона

        Args:
            phone: Номер телефона

        Returns:
            Результат валидации
        """
        if not phone or not phone.strip():
            return ValidationResult(False, "Номер телефона не может быть пустым")

        # Очищаем номер от лишних символов
        clean_phone = re.sub(r'[^\d+]', '', phone.strip())

        # Проверяем российский формат
        if re.match(r'^(\+7|8|7)\d{10}$', clean_phone):
            return ValidationResult(True)

        # Проверяем международный формат
        if re.match(r'^\+\d{10,15}$', clean_phone):
            return ValidationResult(True)

        return ValidationResult(
            False,
            "Неверный формат номера телефона. Используйте формат +7XXXXXXXXXX или 8XXXXXXXXXX"
        )

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Очистка текста от потенциально опасных символов

        Args:
            text: Исходный текст

        Returns:
            Очищенный текст
        """
        if not text:
            return ""

        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)

        # Экранируем специальные символы Telegram
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')

        return text.strip()

    @staticmethod
    def validate_message_length(text: str, max_length: int = 4000) -> ValidationResult:
        """
        Валидация длины сообщения для Telegram

        Args:
            text: Текст сообщения
            max_length: Максимальная длина

        Returns:
            Результат валидации
        """
        if not text:
            return ValidationResult(False, "Сообщение не может быть пустым")

        if len(text) > max_length:
            return ValidationResult(
                False,
                f"Сообщение слишком длинное. Максимум {max_length} символов"
            )

        return ValidationResult(True)