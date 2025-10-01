"""
Состояния FSM (Finite State Machine) для бота
Определяет все состояния пользователя при взаимодействии с ботом
"""

from aiogram.fsm.state import State, StatesGroup


class PostCreation(StatesGroup):
    """Состояния для создания поста"""

    # Выбор типа поста и оплата
    choosing_post_type = State()  # Выбор типа поста (обычный/закреп)
    choosing_payment_method = State()  # Выбор способа оплаты (СБП)
    waiting_payment = State()  # Ожидание оплаты

    # Сбор данных для поста
    waiting_photos = State()  # Ожидание загрузки фотографий
    waiting_title = State()  # Ожидание названия товара
    waiting_condition = State()  # Ожидание состояния товара (новое/б/у)
    waiting_description = State()  # Ожидание описания товара
    waiting_price = State()  # Ожидание цены
    waiting_contact = State()  # Ожидание контактной информации
    confirming_post = State()  # Подтверждение данных поста


class AdminStates(StatesGroup):
    """Состояния для админ-панели"""

    # Работа с платежами
    viewing_payments = State()  # Просмотр платежей на проверке
    processing_payment = State()  # Обработка конкретного платежа

    # Работа с чеками
    receipt_waiting_file = State()  # Ожидание файла чека
    receipt_confirm_send = State()  # Подтверждение отправки

    # Рассылка
    broadcast_text = State()  # Ввод текста для рассылки
    broadcast_confirm = State()  # Подтверждение рассылки

    # Статистика
    viewing_stats = State()  # Просмотр статистики

    # Работа с пользователями
    user_management = State()  # Управление пользователями
    user_details = State()  # Просмотр деталей пользователя


class PaymentStates(StatesGroup):
    """Состояния для работы с платежами"""

    # Процесс оплаты
    payment_method_selected = State()  # Выбран способ оплаты
    payment_pending = State()  # Платеж ожидает подтверждения
    payment_checking = State()  # Платеж на проверке у админа

    # Дополнительные состояния
    payment_failed = State()  # Платеж отклонен
    payment_expired = State()  # Платеж истек

    # Работа с чеками
    uploading_receipt = State()