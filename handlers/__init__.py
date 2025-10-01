"""
Инициализация и регистрация всех обработчиков
"""

from aiogram import Dispatcher

from . import start, payment, post_creation, admin, callback


def register_handlers(dp: Dispatcher) -> None:
    """
    Регистрация всех обработчиков в диспетчере

    Args:
        dp: Диспетчер aiogram
    """
    # Порядок регистрации важен!
    # Более специфичные обработчики должны быть зарегистрированы первыми

    # Админ-обработчики (высокий приоритет)
    dp.include_router(admin.router)

    # Обработчики создания поста (средний приоритет)
    dp.include_router(post_creation.router)

    # Обработчики платежей (средний приоритет)
    dp.include_router(payment.router)

    # Общие обработчики (средний приоритет)
    dp.include_router(start.router)

    # Callback обработчики (низкий приоритет - в самом конце)
    dp.include_router(callback.router)