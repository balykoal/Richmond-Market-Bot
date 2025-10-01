"""
Модуль инициализации базы данных
Содержит функции для подключения к PostgreSQL и инициализации таблиц
"""

from .connector import init_db, close_db, get_connection
from .operations import (
    DatabaseOperations,
    UserOperations,
    PostOperations,
    PaymentOperations,
    AdminOperations,
    ReceiptOperations
)

__all__ = [
    'init_db',
    'close_db',
    'get_connection',
    'DatabaseOperations',
    'UserOperations',
    'PostOperations',
    'PaymentOperations',
    'AdminOperations',
    'ReceiptOperations'
]