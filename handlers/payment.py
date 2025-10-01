"""
Обработчики для работы с платежами
Выбор способа оплаты, создание платежей, проверка статуса
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from database import PaymentOperations
from keyboards.inline import MainKeyboards, NavigationKeyboards
from utils.states import PostCreation
from utils.helpers import format_price, PriceHelper
from services.notification import NotificationService
from config import settings, PaymentStatus

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "create_post")
async def create_post_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Начало создания поста - выбор типа поста
    """
    try:
        await state.set_state(PostCreation.choosing_post_type)

        # Проверяем, является ли пользователь админом
        is_admin = callback.from_user.id == settings.ADMIN_ID

        admin_note = ""
        if is_admin:
            admin_note = "\n\n👑 <b>Режим администратора:</b>\nВаши платежи будут автоматически подтверждены"

        text = f"""
📝 <b>Создание поста</b>

Выберите тип поста для размещения:

📝 <b>Обычный пост ({settings.REGULAR_POST_PRICE}₽)</b>
- Размещается в общей ленте
- Стандартное отображение
- Доступен всем пользователям

📌 <b>Закрепленный пост ({settings.PINNED_POST_PRICE}₽)</b>
- Закрепляется в верхней части канала
- Повышенная видимость
- Больше просмотров и откликов

Какой тип поста вы хотите создать? 🤔{admin_note}
"""

        await callback.message.edit_text(
            text=text,
            reply_markup=MainKeyboards.get_post_type_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в create_post_start: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "back_to_post_type")
async def back_to_post_type(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Возврат к выбору типа поста
    """
    try:
        await state.set_state(PostCreation.choosing_post_type)

        text = f"""
📝 <b>Создание поста</b>

Выберите тип поста для размещения:

📝 <b>Обычный пост ({settings.REGULAR_POST_PRICE}₽)</b>
📌 <b>Закрепленный пост ({settings.PINNED_POST_PRICE}₽)</b>

Какой тип поста вы хотите создать?
"""

        await callback.message.edit_text(
            text=text,
            reply_markup=MainKeyboards.get_post_type_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в back_to_post_type: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("payment:"), PostCreation.choosing_payment_method)
async def payment_method_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора способа оплаты
    """
    try:
        payment_method = callback.data.split(":")[1]

        # Получаем данные из состояния
        data = await state.get_data()
        post_type = data.get('post_type')
        price = PriceHelper.get_post_price(post_type)

        # Создаем платеж
        payment_id = await PaymentOperations.create_payment(
            user_id=callback.from_user.id,
            amount=price,
            method=payment_method,
            currency="RUB"
        )

        if not payment_id:
            await callback.answer("❌ Ошибка создания платежа", show_alert=True)
            return

        # Сохраняем данные о платеже
        await state.update_data(
            payment_method=payment_method,
            payment_id=payment_id,
            price=price
        )
        await state.set_state(PostCreation.waiting_payment)

        # Формируем текст с реквизитами
        payment_info = f"""
🏦 <b>Оплата через СБП</b>

💳 <b>Реквизиты для оплаты:</b>
Номер карты: <code>{settings.CARD_NUMBER}</code>
Получатель: <b>{settings.CARD_HOLDER}</b>

💰 <b>Сумма к оплате:</b> {format_price(price)} ₽

📋 <b>Инструкция:</b>
1. Переведите точную сумму на указанную карту
2. Нажмите "Проверить платеж"
3. Дождитесь подтверждения от администратора
4. Приступайте к созданию поста!

⚠️ <b>Важно:</b>
- Переводите точную сумму
- Сохраните чек об оплате
- Платеж проверяется администратором

Платеж №{payment_id}
"""

        await callback.message.edit_text(
            text=payment_info,
            reply_markup=MainKeyboards.get_payment_status_menu(payment_id),
            parse_mode="HTML"
        )

        # Уведомляем админа о новом платеже с кнопкой
        notification_service = NotificationService(callback.bot)
        await notification_service.notify_admin_new_payment(payment_id)

        await callback.answer("💳 Реквизиты для оплаты отправлены")

    except Exception as e:
        logger.error(f"Ошибка в payment_method_selected: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("check_payment:"), PostCreation.waiting_payment)
async def check_payment_status(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Проверка статуса платежа
    """
    try:
        payment_id = int(callback.data.split(":")[1])

        # Получаем данные о платеже
        payment = await PaymentOperations.get_payment(payment_id)

        if not payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        # Проверяем принадлежность платежа пользователю
        if payment['user_id'] != callback.from_user.id:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        status = payment['status']
        logger.info(f"Проверка платежа {payment_id}, статус: {status}")

        if status == PaymentStatus.PENDING:
            # Переводим в статус "на проверке"
            success = await PaymentOperations.update_payment_status(payment_id, PaymentStatus.CHECKING)
            if success:
                await callback.answer("🔍 Платеж отправлен на проверку администратору")

            # Обновляем сообщение
            text = f"""
🔍 <b>Платеж на проверке</b>

Платеж №{payment_id} отправлен на проверку администратору.

⏱ <b>Время проверки:</b> 5-15 минут
📞 <b>Вопросы:</b> @balykoal

Мы уведомим вас, как только платеж будет подтвержден! 🔔
"""

            await callback.message.edit_text(
                text=text,
                reply_markup=NavigationKeyboards.get_back_to_main_menu(),
                parse_mode="HTML"
            )

        elif status == PaymentStatus.CHECKING:
            await callback.answer("🔍 Платеж уже на проверке у администратора")

        elif status == PaymentStatus.CONFIRMED:
            # Получаем все данные из состояния
            data = await state.get_data()
            post_type = data.get('post_type')
            price = data.get('price')

            # Сохраняем все данные в состояние для продолжения создания поста
            await state.update_data(
                payment_id=payment_id,
                price=price,
                post_type=post_type,
                photos=[]  # Инициализируем пустой список фотографий
            )

            # Переходим к созданию поста
            await state.set_state(PostCreation.waiting_photos)

            text = f"""
✅ <b>Платеж подтвержден!</b>

Отлично! Ваш платеж №{payment_id} подтвержден.

Теперь приступим к созданию поста! 📝

📸 <b>Шаг 1: Загрузите фотографии</b>

Отправьте от {settings.MIN_PHOTOS} до {settings.MAX_PHOTOS} фотографий вашего товара.

💡 <b>Советы для хороших фото:</b>
- Делайте фото при хорошем освещении
- Показывайте товар с разных ракурсов
- Включите фото дефектов (если есть)
- Фотографии должны быть четкими

Загрузите первую фотографию 📸
"""

            await callback.message.edit_text(text=text, parse_mode="HTML")
            await callback.answer("✅ Платеж подтвержден! Переходите к созданию поста")

        elif status == PaymentStatus.REJECTED:
            reason = payment.get('rejection_reason', 'Не указана')

            text = f"""
❌ <b>Платеж отклонен</b>

Платеж №{payment_id} был отклонен администратором.

<b>Причина:</b> {reason}

Пожалуйста, свяжитесь с поддержкой для выяснения деталей: @balykoal

Вы можете создать новый платеж, нажав "Разместить пост" в главном меню.
"""

            await callback.message.edit_text(
                text=text,
                reply_markup=NavigationKeyboards.get_back_to_main_menu(),
                parse_mode="HTML"
            )

            await callback.answer("❌ Платеж отклонен")

        else:
            await callback.answer("❓ Неизвестный статус платежа")

    except Exception as e:
        logger.error(f"Ошибка в check_payment_status: {e}")
        await callback.answer("❌ Произошла ошибка при проверке платежа", show_alert=True)


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Отмена платежа
    """
    try:
        # Очищаем состояние
        await state.clear()

        text = """
❌ <b>Платеж отменен</b>

Вы отменили процесс оплаты. Платеж не был создан.

Если передумаете, можете начать заново, нажав "Разместить пост" в главном меню! 😊
"""

        await callback.message.edit_text(
            text=text,
            reply_markup=MainKeyboards.get_main_menu(callback.from_user.id, settings.ADMIN_ID),
            parse_mode="HTML"
        )

        await callback.answer("❌ Платеж отменен")

    except Exception as e:
        logger.error(f"Ошибка в cancel_payment: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)