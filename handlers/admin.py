"""\
Обработчики админ-панели
Управление платежами, пользователями, статистика и рассылки
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from pathlib import Path

from database import PaymentOperations, AdminOperations, UserOperations, ReceiptOperations
from keyboards.inline import AdminKeyboards, NavigationKeyboards, MainKeyboards
from utils.states import AdminStates
from utils.helpers import MessageFormatter, format_user_info, format_price, format_datetime
from utils.backup import BackupManager
from services.notification import NotificationService
from config import settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext) -> None:
    """
    Главная админ-панель (только для администратора)

    Args:
        message: Сообщение команды
        state: Состояние FSM
    """
    try:
        # Проверяем права администратора
        if message.from_user.id != settings.ADMIN_ID:
            await message.answer("❌ У вас нет прав доступа к админ-панели")
            return

        # Очищаем состояние
        await state.clear()

        # Получаем базовую статистику
        stats = await AdminOperations.get_stats()
        pending_payments = await PaymentOperations.get_pending_payments()

        text = f"""\
👑 <b>Панель администратора</b>

📊 <b>Быстрая статистика:</b>
• Пользователей: {stats.get('users', {}).get('total', 0)}
• Постов: {stats.get('posts', {}).get('total', 0)}
• Платежей на проверке: {len(pending_payments)}
• Доход: {stats.get('payments', {}).get('revenue', 0)} ₽

Выберите действие: 👇\
"""

        await message.answer(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

        # Логируем вход в админ-панель
        await AdminOperations.log_admin_action(
            admin_id=message.from_user.id,
            action="admin_panel_access",
            details={"ip": "unknown", "timestamp": message.date.isoformat()}
        )

    except Exception as e:
        logger.error(f"Ошибка в admin_panel: {e}")
        await message.answer("❌ Произошла ошибка при загрузке админ-панели")


@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery) -> None:
    """
    Возврат в админ-меню

    Args:
        callback: Callback запрос
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем обновленную статистику
        stats = await AdminOperations.get_stats()
        pending_payments = await PaymentOperations.get_pending_payments()

        text = f"""\
👑 <b>Панель администратора</b>

📊 <b>Актуальная статистика:</b>
• Пользователей: {stats.get('users', {}).get('total', 0)}
• Новых сегодня: {stats.get('users', {}).get('new_today', 0)}
• Постов: {stats.get('posts', {}).get('total', 0)}
• Платежей на проверке: {len(pending_payments)}
• Общий доход: {stats.get('payments', {}).get('revenue', 0)} ₽

Выберите действие: 👇\
"""

        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в admin_menu_callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "switch_to_user_mode")
async def switch_to_user_mode_callback(callback: CallbackQuery, state: FSMContext):
    """Переключение в режим пользователя через callback"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        await state.clear()
        await callback.message.edit_text(
            "👤 <b>Режим пользователя</b>\n\nТеперь вы можете использовать бот как обычный пользователь.",
            reply_markup=MainKeyboards.get_main_menu(callback.from_user.id, settings.ADMIN_ID),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в switch_to_user_mode_callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "admin_payments")
async def admin_payments(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Просмотр платежей на проверке
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        await state.set_state(AdminStates.viewing_payments)

        # Получаем платежи на проверке
        try:
            pending_payments = await PaymentOperations.get_pending_payments()
            logger.info(f"Найдено платежей на проверке: {len(pending_payments)}")
        except Exception as e:
            logger.error(f"Ошибка получения платежей: {e}")
            pending_payments = []

        # Добавляем timestamp чтобы избежать ошибки "message is not modified"
        import time
        timestamp = int(time.time())

        if not pending_payments:
            text = f"""\
✅ <b>Платежи на проверке</b>

Отлично! Все платежи обработаны.
Новые платежи появятся здесь автоматически.

Проверьте позже или используйте кнопку "Обновить" 🔄

<code>#{timestamp}</code>\
"""
        else:
            text = f"""\
💳 <b>Платежи на проверке</b>

Найдено платежей: <b>{len(pending_payments)}</b>

Выберите платеж для модерации:

<code>#{timestamp}</code>\
"""

        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_payments_list_menu(pending_payments),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в admin_payments: {e}")
        await callback.answer("❌ Произошла ошибка при загрузке платежей", show_alert=True)

@router.callback_query(F.data.startswith("moderate_payment:"))
async def moderate_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Модерация конкретного платежа

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        payment_id = int(callback.data.split(":")[1])

        # Получаем данные платежа
        payment = await PaymentOperations.get_payment(payment_id)
        if not payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        # Получаем данные пользователя
        user = await UserOperations.get_user(payment['user_id'])

        # Сохраняем ID платежа в состояние
        await state.update_data(current_payment_id=payment_id)
        await state.set_state(AdminStates.processing_payment)

        # Форматируем информацию о платеже
        payment_info = MessageFormatter.format_payment_info(payment, user)

        method_text = "🏦 СБП" if payment['method'] == 'sbp' else "₿ Крипта"

        text = f"""
🔍 <b>Модерация платежа</b>

{payment_info}

<b>📋 Дополнительная информация:</b>
• Статус: На проверке
• Метод: {method_text}

<b>Действия:</b>
✅ Подтвердить - платеж корректный
❌ Отклонить - есть проблемы с платежом

Что делать с этим платежом? 🤔
        """

        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_payment_moderation_menu(payment_id),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в moderate_payment: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("confirm_payment:"))
async def confirm_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Подтверждение платежа

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        payment_id = int(callback.data.split(":")[1])

        # Подтверждаем платеж
        success = await PaymentOperations.confirm_payment(payment_id, callback.from_user.id)

        if success:
            # Получаем данные платежа для уведомления
            payment = await PaymentOperations.get_payment(payment_id)

            # Уведомляем пользователя с кнопкой для создания поста
            notification_service = NotificationService(callback.bot)
            await notification_service.notify_payment_confirmed_with_post_creation(payment_id)

            # Логируем действие
            await AdminOperations.log_admin_action(
                admin_id=callback.from_user.id,
                action="payment_confirmed",
                details={"payment_id": payment_id, "amount": float(payment['amount'])},
                target_payment_id=payment_id
            )

            text = f"""
✅ <b>Платеж подтвержден!</b>

Платеж №{payment_id} успешно подтвержден.

✅ Пользователь уведомлен
✅ Отправлена кнопка для создания поста
✅ Действие занесено в логи

Отличная работа! 👍
"""
            await callback.message.edit_text(
                text=text,
                reply_markup=NavigationKeyboards.get_back_to_main_menu(),
                parse_mode="HTML"
            )

            await callback.answer("✅ Платеж подтвержден!")

        else:
            await callback.answer("❌ Ошибка подтверждения платежа", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в confirm_payment: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("reject_payment:"))
async def reject_payment_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Начало процесса отклонения платежа

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        payment_id = int(callback.data.split(":")[1])

        # Сохраняем ID платежа
        await state.update_data(rejecting_payment_id=payment_id)

        text = f"""
❌ <b>Отклонение платежа №{payment_id}</b>

Укажите причину отклонения платежа.
Эта информация будет отправлена пользователю.

<b>Примеры причин:</b>
• Неполная сумма платежа
• Платеж не найден
• Технические проблемы
• Некорректные реквизиты

<b>Введите причину отклонения:</b> 👇
        """

        await callback.message.edit_text(text=text, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в reject_payment_start: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(F.text, AdminStates.processing_payment)
async def reject_payment_reason(message: Message, state: FSMContext) -> None:
    """
    Получение причины отклонения платежа

    Args:
        message: Сообщение с причиной
        state: Состояние FSM
    """
    try:
        if message.from_user.id != settings.ADMIN_ID:
            await message.answer("❌ У вас нет прав доступа")
            return

        data = await state.get_data()
        payment_id = data.get('rejecting_payment_id')

        if not payment_id:
            await message.answer("❌ Ошибка: платеж не найден")
            return

        reason = message.text.strip()

        # Отклоняем платеж
        success = await PaymentOperations.reject_payment(payment_id, message.from_user.id, reason)

        if success:
            # Уведомляем пользователя
            notification_service = NotificationService(message.bot)
            await notification_service.notify_payment_rejected(payment_id, reason)

            # Логируем действие
            await AdminOperations.log_admin_action(
                admin_id=message.from_user.id,
                action="payment_rejected",
                details={"payment_id": payment_id, "reason": reason},
                target_payment_id=payment_id
            )

            text = f"""
❌ <b>Платеж отклонен!</b>

Платеж №{payment_id} отклонен по причине:
"{reason}"

✅ Пользователь уведомлен
✅ Причина указана в уведомлении
✅ Действие занесено в логи

Платеж обработан. 📝
            """

            from keyboards.inline import AdminKeyboards
            await message.answer(
                text=text,
                reply_markup=AdminKeyboards.get_admin_menu(),
                parse_mode="HTML"
            )

        else:
            await message.answer("❌ Ошибка отклонения платежа")

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в reject_payment_reason: {e}")
        await message.answer("❌ Произошла ошибка при отклонении платежа")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery) -> None:
    """
    Показ детальной статистики

    Args:
        callback: Callback запрос
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем подробную статистику
        stats = await AdminOperations.get_stats()

        # Форматируем статистику
        formatted_stats = MessageFormatter.format_admin_stats(stats)

        text = f"""
{formatted_stats}

📈 <b>Дополнительная информация:</b>
• Бот работает стабильно
• Все системы функционируют
• Последнее обновление: сейчас

<i>Обновлено: {format_datetime(None)}</i>
        """

        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

        await callback.answer("📊 Статистика обновлена")

    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Начало создания рассылки

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        await state.set_state(AdminStates.broadcast_text)

        # Получаем количество пользователей
        users = await UserOperations.get_all_users()

        text = f"""\
📢 <b>Создание рассылки</b>

Сейчас в боте <b>{len(users)}</b> пользователей.

Напишите текст сообщения для рассылки всем пользователям:

⚠️ <b>Важно:</b>
• Сообщение будет отправлено ВСЕМ пользователям
• Используйте HTML разметку
• Избегайте спама и рекламы
• Проверьте текст перед отправкой

<b>Введите текст рассылки:</b> 👇\
"""

        await callback.message.edit_text(text=text, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в admin_broadcast_start: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.message(F.text, AdminStates.broadcast_text)
async def broadcast_text_received(message: Message, state: FSMContext) -> None:
    """
    Получение текста для рассылки

    Args:
        message: Сообщение с текстом
        state: Состояние FSM
    """
    try:
        if message.from_user.id != settings.ADMIN_ID:
            await message.answer("❌ У вас нет прав доступа")
            return

        broadcast_text = message.text.strip()

        # Сохраняем текст рассылки
        await state.update_data(broadcast_text=broadcast_text)
        await state.set_state(AdminStates.broadcast_confirm)

        # Получаем количество пользователей
        users = await UserOperations.get_all_users()

        text = f"""\
📢 <b>Подтверждение рассылки</b>

<b>Текст сообщения:</b>
─────────────────────
{broadcast_text}
─────────────────────

<b>📊 Статистика:</b>
• Получателей: {len(users)} пользователей
• Примерное время: ~{len(users) * 0.05 / 60:.1f} минут

⚠️ <b>Внимание!</b>
Это действие нельзя отменить после запуска!

Отправить рассылку всем пользователям? 🤔\
"""

        from keyboards.inline import AdminKeyboards
        await message.answer(
            text=text,
            reply_markup=AdminKeyboards.get_broadcast_confirmation_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка в broadcast_text_received: {e}")
        await message.answer("❌ Произошла ошибка при обработке текста")

@router.callback_query(F.data == "confirm_broadcast", AdminStates.broadcast_confirm)
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Подтверждение и запуск рассылки

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        data = await state.get_data()
        broadcast_text = data.get('broadcast_text')

        if not broadcast_text:
            await callback.answer("❌ Текст рассылки не найден", show_alert=True)
            return

        # Очищаем состояние
        await state.clear()

        # Уведомляем о начале рассылки
        await callback.message.edit_text(
            text="🚀 <b>Рассылка запущена!</b>\n\nПожалуйста, подождите...",
            parse_mode="HTML"
        )

        await callback.answer("🚀 Рассылка началась!")

        # Запускаем рассылку асинхронно
        notification_service = NotificationService(callback.bot)
        stats = await notification_service.broadcast_message(broadcast_text)

        # Логируем рассылку (сериализуем details в JSON)
        await AdminOperations.log_admin_action(
            admin_id=callback.from_user.id,
            action="broadcast_sent",
            details={
                "message_length": len(broadcast_text),
                "recipients": stats['total'],
                "sent": stats['sent'],
                "failed": stats['failed']
            }
        )

        # Отправляем финальный отчет
        final_text = f"""\
✅ <b>Рассылка завершена!</b>

📊 <b>Результаты:</b>
• Всего получателей: {stats['total']}
• Доставлено: {stats['sent']}
• Заблокировали бота: {stats['blocked']}
• Ошибки доставки: {stats['failed']}

📈 <b>Успешность:</b> {round(stats['sent'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0}%

Отлично! Рассылка выполнена 🎉\
"""

        from keyboards.inline import AdminKeyboards
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=final_text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка в confirm_broadcast: {e}")
        await callback.answer("❌ Произошла ошибка при рассылке", show_alert=True)

@router.callback_query(F.data == "cancel_broadcast", AdminStates.broadcast_confirm)
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Отмена рассылки

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        await state.clear()

        text = """
❌ <b>Рассылка отменена</b>

Рассылка была отменена.
Никто не получил сообщения.

Можете создать новую рассылку в любое время! 😊
        """

        from keyboards.inline import AdminKeyboards
        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

        await callback.answer("❌ Рассылка отменена")

    except Exception as e:
        logger.error(f"Ошибка в cancel_broadcast: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery) -> None:
    """
    Управление пользователями

    Args:
        callback: Callback запрос
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем статистику пользователей
        users = await UserOperations.get_all_users()
        total_users = len(users)

        # Считаем активных пользователей (с постами)
        active_users = len([u for u in users if u.get('post_count', 0) > 0])

        # Последние 5 пользователей
        recent_users = sorted(users, key=lambda x: x.get('reg_date', ''), reverse=True)[:5]

        text = f"""
👥 <b>Управление пользователями</b>

📊 <b>Статистика:</b>
• Всего пользователей: {total_users}
• Активных (с постами): {active_users}
• Процент активности: {round(active_users/total_users*100, 1) if total_users > 0 else 0}%

👤 <b>Последние пользователи:</b>
        """

        for user in recent_users:
            user_info = format_user_info(user)
            reg_date = format_datetime(user.get('reg_date'))
            posts = user.get('post_count', 0)

            text += f"""
• {user_info}
  Регистрация: {reg_date}
  Постов: {posts}
            """

        text += f"""

<b>🔧 Функции в разработке:</b>
• Детальный профиль пользователя
• Блокировка пользователей
• Экспорт данных

<i>Используйте другие разделы админ-панели</i>
        """

        from keyboards.inline import AdminKeyboards
        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в admin_users: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery) -> None:
    """
    Просмотр логов администратора

    Args:
        callback: Callback запрос
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем последние логи
        logs = await AdminOperations.get_admin_logs(limit=10)

        text = f"""\
📋 <b>Логи администратора</b>

<b>Последние {len(logs)} действий:</b>

"""

        if logs:
            for log in logs:
                action_text = {
                    'admin_panel_access': '🔑 Вход в панель',
                    'payment_confirmed': '✅ Платеж подтвержден',
                    'payment_rejected': '❌ Платеж отклонен',
                    'broadcast_sent': '📢 Рассылка отправлена'
                }.get(log['action'], f"❓ {log['action']}")

                timestamp = format_datetime(log['timestamp'])

                text += f"""\
{action_text}
⏰ {timestamp}
"""

                # Добавляем детали если есть
                details = log.get('details', {})
                if details and isinstance(details, dict):
                    if 'payment_id' in details:
                        text += f"💳 Платеж: #{details['payment_id']}\n"
                    if 'amount' in details:
                        text += f"💰 Сумма: {details['amount']} ₽\n"
                    if 'recipients' in details:
                        text += f"📨 Получателей: {details['recipients']}\n"
                    if 'reason' in details:
                        text += f"📝 Причина: {details['reason'][:50]}...\n"

                text += "\n"
        else:
            text += "Логи отсутствуют."

        text += f"""\
<b>📊 Информация:</b>
• Логи хранятся в базе данных
• Автоматическое логирование всех действий
• История доступна в любое время

<i>Показаны последние 10 записей</i>\
"""

        from keyboards.inline import AdminKeyboards
        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в admin_logs: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# Обработчик неправильных сообщений в админ-состояниях
@router.message(F.text, StateFilter(AdminStates))
async def wrong_admin_input(message: Message, state: FSMContext) -> None:
    """
    Обработчик неправильного ввода в админ-состояниях

    Args:
        message: Сообщение
        state: Состояние FSM
    """
    try:
        if message.from_user.id != settings.ADMIN_ID:
            return

        current_state = await state.get_state()

        if current_state == AdminStates.broadcast_text:
            await message.answer(
                "📢 Пожалуйста, отправьте текст для рассылки.\n"
                "Используйте обычное текстовое сообщение."
            )
        elif current_state == AdminStates.processing_payment:
            # Проверяем, отклоняем ли мы платеж
            data = await state.get_data()
            if data.get('rejecting_payment_id'):
                await message.answer(
                    "❌ Пожалуйста, укажите причину отклонения платежа.\n"
                    "Отправьте текстовое сообщение с причиной."
                )
            else:
                await message.answer(
                    "💳 Используйте кнопки для работы с платежами."
                )
        else:
            await message.answer("🤖 Используйте кнопки для навигации по админ-панели.")

    except Exception as e:
        logger.error(f"Ошибка в wrong_admin_input: {e}")
        await message.answer("❌ Произошла ошибка")


@router.callback_query(F.data == "admin_receipts")
async def admin_receipts_main(callback: CallbackQuery) -> None:
    """Главное меню управления чеками"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем статистику
        stats = await ReceiptOperations.get_receipt_stats()

        text = f"""
🧾 <b>Управление чеками</b>

📊 <b>Статистика:</b>
• Всего подтвержденных платежей: {stats['total_payments']}
• Чеков отправлено: {stats['sent_receipts']}
• Ожидают отправки: {stats['pending_receipts']}
• Отправлено сегодня: {stats['today_receipts']}

Выберите действие:
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Без чеков", callback_data="show_no_receipts"),
                InlineKeyboardButton(text="✅ С чеками", callback_data="show_with_receipts")
            ],
            [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_menu")]
        ])

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в admin_receipts_main: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "show_no_receipts")
async def show_payments_without_receipts(callback: CallbackQuery) -> None:
    """Показать платежи без чеков"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем платежи без чеков
        payments = await ReceiptOperations.get_payments_without_receipts()

        if not payments:
            text = """
✅ <b>Отлично!</b>

Все подтвержденные платежи имеют отправленные чеки.
Новые платежи появятся здесь автоматически.
"""
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="show_no_receipts")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_receipts")]
            ])
        else:
            text = f"""
❌ <b>Платежи без чеков ({len(payments)} шт.)</b>

Нажмите на платеж, чтобы отправить чек:
"""

            keyboard_buttons = []

            # Добавляем кнопки с платежами
            for payment in payments:
                user_name = payment.get('first_name', 'Без имени')
                if payment.get('username'):
                    user_name = f"@{payment['username']}"

                button_text = f"💳 {payment['amount']}₽ - {user_name}"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"send_receipt:{payment['payment_id']}"
                    )
                ])

            # Кнопки управления
            keyboard_buttons.append([
                InlineKeyboardButton(text="🔄 Обновить", callback_data="show_no_receipts")
            ])
            keyboard_buttons.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_receipts")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в show_payments_without_receipts: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "show_with_receipts")
async def show_payments_with_receipts(callback: CallbackQuery) -> None:
    """Показать платежи с отправленными чеками"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        # Получаем платежи с чеками
        payments = await ReceiptOperations.get_payments_with_receipts()

        if not payments:
            text = """
📋 <b>История чеков пуста</b>

Пока не отправлено ни одного чека.
"""
        else:
            text = f"""
✅ <b>Отправленные чеки ({len(payments)} шт.)</b>

Последние отправленные чеки:

"""

            # Показываем последние чеки
            for payment in payments[:10]:
                user_name = payment.get('first_name', 'Без имени')
                if payment.get('username'):
                    user_name = f"@{payment['username']}"

                file_icon = "📄" if payment['file_type'] == 'document' else "📸"

                text += f"""
{file_icon} <b>{payment['amount']}₽</b> - {user_name}
📅 {format_datetime(payment['sent_at'])}

"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="show_with_receipts")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_receipts")]
        ])

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в show_payments_with_receipts: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("send_receipt:"))
async def prepare_send_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    """Подготовка к отправке чека"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        payment_id = int(callback.data.split(":")[1])

        # Получаем данные платежа
        payment = await PaymentOperations.get_payment(payment_id)
        if not payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        # Проверяем, что чек еще не отправлен
        if await ReceiptOperations.payment_has_receipt(payment_id):
            await callback.answer("⚠️ Чек уже отправлен для этого платежа", show_alert=True)
            return

        # Получаем данные пользователя
        user = await UserOperations.get_user(payment['user_id'])
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Сохраняем данные в состояние
        await state.update_data(
            receipt_payment_id=payment_id,
            receipt_user_id=payment['user_id']
        )
        await state.set_state(AdminStates.receipt_waiting_file)

        user_info = f"{user.get('first_name', 'Без имени')}"
        if user.get('username'):
            user_info += f" (@{user['username']})"

        text = f"""
📨 <b>Отправка чека</b>

💳 <b>Платеж №{payment_id}</b>
👤 <b>Пользователь:</b> {user_info}
💰 <b>Сумма:</b> {format_price(payment['amount'])} ₽
📅 <b>Дата платежа:</b> {format_datetime(payment['created_at'])}

📎 <b>Отправьте файл чека:</b>
• Фотографию чека 📸
• PDF документ 📄
• Другие документы

<i>Ожидаю файл...</i>
"""

        await callback.message.edit_text(text=text, parse_mode="HTML")
        await callback.answer("📎 Отправьте файл чека...")

    except Exception as e:
        logger.error(f"Ошибка в prepare_send_receipt: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(F.document | F.photo, AdminStates.receipt_waiting_file)
async def handle_receipt_file(message: Message, state: FSMContext) -> None:
    """Обработка файла чека и отправка пользователю"""
    try:
        if message.from_user.id != settings.ADMIN_ID:
            await state.clear()
            return

        # Получаем данные из состояния
        data = await state.get_data()
        payment_id = data.get('receipt_payment_id')
        user_id = data.get('receipt_user_id')

        if not payment_id or not user_id:
            await message.answer("❌ Ошибка: данные не найдены")
            await state.clear()
            return

        # Определяем тип файла
        file_id = None
        file_type = None
        file_name = None

        if message.document:
            file_id = message.document.file_id
            file_type = "document"
            file_name = message.document.file_name or "receipt.pdf"
        elif message.photo:
            file_id = message.photo[-1].file_id  # самое большое фото
            file_type = "photo"
            file_name = "receipt.jpg"

        if not file_id:
            await message.answer("❌ Поддерживаются только фото и документы")
            return

        # Получаем данные платежа и пользователя
        payment = await PaymentOperations.get_payment(payment_id)
        user = await UserOperations.get_user(user_id)

        receipt_text = f"""
🧾 <b>Чек об оплате</b>

💳 <b>Платеж №{payment_id}</b>
💰 <b>Сумма:</b> {format_price(payment['amount'])} ₽
📅 <b>Дата:</b> {format_datetime(payment['created_at'])}
🛍 <b>Услуга:</b> Размещение объявления в @richmondmarket

<b>Спасибо за использование нашего сервиса!</b>
По вопросам: @balykoal
"""

        try:
            # Сначала пробуем по file_id
            if file_type == "document":
                await message.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=receipt_text,
                    parse_mode="HTML"
                )
            else:
                await message.bot.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption=receipt_text,
                    parse_mode="HTML"
                )

        except Exception as send_error:
            logger.error(f"Ошибка отправки по file_id: {send_error}. Пробую через download...")

            # Скачиваем и отправляем как новый файл
            downloaded = await message.bot.download(file_id)
            input_file = FSInputFile(downloaded.name)

            if file_type == "document":
                await message.bot.send_document(
                    chat_id=user_id,
                    document=input_file,
                    caption=receipt_text,
                    parse_mode="HTML"
                )
            else:
                await message.bot.send_photo(
                    chat_id=user_id,
                    photo=input_file,
                    caption=receipt_text,
                    parse_mode="HTML"
                )

        # Сохраняем в БД
        receipt_id = await ReceiptOperations.create_receipt(
            payment_id=payment_id,
            user_id=user_id,
            admin_id=message.from_user.id,
            file_id=file_id,
            file_type=file_type,
            file_name=file_name
        )

        # Логируем
        await AdminOperations.log_admin_action(
            admin_id=message.from_user.id,
            action="receipt_sent",
            details={
                "receipt_id": receipt_id,
                "payment_id": payment_id,
                "file_type": file_type
            },
            target_user_id=user_id,
            target_payment_id=payment_id
        )

        # Успешное сообщение админу
        user_info = f"{user.get('first_name', 'Без имени')}"
        if user.get('username'):
            user_info += f" (@{user['username']})"

        success_text = f"""
✅ <b>Чек отправлен!</b>

👤 <b>Пользователь:</b> {user_info}
💳 <b>Платеж:</b> №{payment_id}
💰 <b>Сумма:</b> {format_price(payment['amount'])} ₽
📎 <b>Файл:</b> {file_name}

Чек успешно доставлен пользователю и сохранен в системе.
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Управление чеками", callback_data="admin_receipts")],
            [InlineKeyboardButton(text="🏠 Главная", callback_data="admin_menu")]
        ])

        await message.answer(
            text=success_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в handle_receipt_file: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке файла: {e}")
        await state.clear()

# Обработчик неправильного типа файла в состоянии ожидания чека
@router.message(AdminStates.receipt_waiting_file)
async def wrong_receipt_file_type(message: Message, state: FSMContext) -> None:
    """Обработчик неправильного типа при ожидании файла чека"""
    if message.from_user.id != settings.ADMIN_ID:
        await state.clear()
        return

    await message.answer(
        "📎 Пожалуйста, отправьте файл чека:\n"
        "• Фотографию 📸\n"
        "• PDF документ 📄\n"
        "• Другие документы"
    )

#BACKUP
@router.callback_query(F.data == "admin_backups")
async def admin_backups_main(callback: CallbackQuery) -> None:
    """Главное меню управления бэкапами"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        backup_manager = BackupManager()
        stats = await backup_manager.get_backup_stats()

        newest = stats.get('newest_backup')
        newest_str = newest['created'].strftime('%d.%m.%Y %H:%M') if newest else "Нет"

        text = f"""
💾 <b>Управление бэкапами Richmond Market</b>

📊 <b>Статистика:</b>
• Всего бэкапов: {stats.get('total_backups', 0)}
• Общий размер: {stats.get('total_size_mb', 0)} MB
• Последний бэкап: {newest_str}

<b>Функции:</b>
• Создание бэкапа базы данных
• Просмотр списка бэкапов
• Восстановление из бэкапа
• Автоматическая очистка (каждые 7 дней)

⚡ <b>Автоматические бэкапы:</b> Ежедневно в 03:00

Выберите действие:
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 Создать бэкап", callback_data="create_backup"),
                InlineKeyboardButton(text="📋 Список бэкапов", callback_data="list_backups")
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="backup_stats"),
                InlineKeyboardButton(text="🧹 Очистить старые", callback_data="cleanup_backups")
            ],
            [
                InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_menu")
            ]
        ])

        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                pass
            else:
                raise
        await callback.answer()

    except Exception as e:
        logger.exception(f"Ошибка в admin_backups_main: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "create_backup")
async def create_backup_handler(callback: CallbackQuery) -> None:
    """Создание бэкапа (вручную из админки)"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        await callback.answer("🔄 Создание бэкапа...")
        try:
            await callback.message.edit_text(
                text="💾 <b>Создание бэкапа Richmond Market...</b>\n\n🔄 Подготовка данных...",
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass

        backup_manager = BackupManager()
        result = await backup_manager.create_backup()

        if result.get('success'):
            size_mb = round(result['size'] / 1024 / 1024, 2)
            text = f"""
✅ <b>Бэкап создан успешно!</b>

📊 <b>Информация:</b>
• Время создания: {result['created'].strftime('%d.%m.%Y %H:%M:%S')}
• Размер файла: {size_mb} MB
• Файл: {result['name']}
• Сжатие: ✅ Включено (gzip -9)

Бэкап сохранен в папке /backups.
"""
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Список бэкапов", callback_data="list_backups")],
                [InlineKeyboardButton(text="📊 Статистика", callback_data="backup_stats")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")]
            ])
        else:
            text = f"""
❌ <b>Ошибка создания бэкапа!</b>

<b>Причина:</b> {result.get('message', 'Неизвестная ошибка')}

Подробности в логах сервера.
"""
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")]
            ])

        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.exception(f"Ошибка в create_backup_handler: {e}")
        await callback.answer("❌ Произошла ошибка при создании бэкапа", show_alert=True)


@router.callback_query(F.data == "list_backups")
async def list_backups_handler(callback: CallbackQuery) -> None:
    """Показать список бэкапов с действиями"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        bm = BackupManager()
        backups = bm.get_backup_list()

        if not backups:
            await callback.message.edit_text(
                text="📁 Список бэкапов пуст.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")]
                ]),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Формируем текст и клавиатуру: показываем до 20 последних
        text = "📁 <b>Список бэкапов</b>\n\n"
        kb_rows = []
        for b in backups[:20]:
            created = b['created'].strftime('%d.%m.%Y %H:%M')
            text += f"• {b['name']} — {b['size_mb']} MB — {created}\n"
            kb_rows.append([
                InlineKeyboardButton(text=f"⬇️ {b['name'][:20]}", callback_data=f"backup_download:{b['name']}"),
                InlineKeyboardButton(text="⚠️", callback_data=f"backup_actions:{b['name']}")
            ])

        kb_rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.exception(f"Ошибка в list_backups_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup_actions:"))
async def backup_actions_handler(callback: CallbackQuery) -> None:
    """Меню действий над конкретным бэкапом"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        _, name = callback.data.split(":", 1)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ Скачать", callback_data=f"backup_download:{name}")],
            [InlineKeyboardButton(text="♻️ Восстановить (confirm)", callback_data=f"backup_confirm_restore:{name}")],
            [InlineKeyboardButton(text="🗑 Удалить (confirm)", callback_data=f"backup_confirm_delete:{name}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="list_backups")]
        ])

        await callback.message.edit_text(
            text=f"📁 <b>Действия для:</b>\n{name}",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.exception(f"Ошибка в backup_actions_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup_download:"))
async def backup_download_handler(callback: CallbackQuery) -> None:
    """Скачать бэкап (отправить файл админу)"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return

        _, name = callback.data.split(":", 1)
        bm = BackupManager()
        path = Path(bm.backup_dir) / name

        if not path.exists():
            await callback.answer("❌ Файл не найден", show_alert=True)
            return

        await callback.message.answer_document(document=FSInputFile(str(path)), caption=f"📥 Бэкап: {name}")
        await callback.answer()

    except Exception as e:
        logger.exception(f"Ошибка в backup_download_handler: {e}")
        await callback.answer("❌ Не удалось отправить файл", show_alert=True)


@router.callback_query(F.data.startswith("backup_confirm_delete:"))
async def backup_confirm_delete(callback: CallbackQuery) -> None:
    """Подтверждение удаления бэкапа"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        _, name = callback.data.split(":", 1)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"backup_delete:{name}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="list_backups")]
        ])
        await callback.message.edit_text(text=f"⚠️ Удалить бэкап <b>{name}</b>?", reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.exception(f"Ошибка в backup_confirm_delete: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup_delete:"))
async def backup_delete_handler(callback: CallbackQuery) -> None:
    """Удалить бэкап"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        _, name = callback.data.split(":", 1)
        bm = BackupManager()
        res = await bm.delete_backup(name)
        if res.get('success'):
            await callback.message.edit_text(text=f"🗑 Бэкап <b>{name}</b> удалён.\n{res.get('message')}", parse_mode="HTML",
                                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="list_backups")]]))
        else:
            await callback.answer(f"❌ Ошибка удаления: {res.get('message')}", show_alert=True)
    except Exception as e:
        logger.exception(f"Ошибка в backup_delete_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup_confirm_restore:"))
async def backup_confirm_restore(callback: CallbackQuery) -> None:
    """Подтверждение восстановления (крайне осторожно)"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        _, name = callback.data.split(":", 1)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, восстановить", callback_data=f"backup_restore:{name}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="list_backups")]
        ])
        await callback.message.edit_text(text=f"🚨 Восстановление из бэкапа <b>{name}</b> перезапишет базу. Продолжить?", reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.exception(f"Ошибка в backup_confirm_restore: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup_restore:"))
async def backup_restore_handler(callback: CallbackQuery) -> None:
    """Выполнить восстановление из бэкапа (внимание: операция рискованная)"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        _, name = callback.data.split(":", 1)
        bm = BackupManager()
        await callback.message.edit_text(text=f"♻️ Восстановление из бэкапа {name}...\nЭто может занять время.", parse_mode="HTML")
        res = await bm.restore_backup(name)
        if res.get('success'):
            await callback.message.edit_text(text=f"✅ Восстановление завершено: {res.get('message')}", parse_mode="HTML",
                                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")]]))
        else:
            await callback.message.edit_text(text=f"❌ Ошибка восстановления: {res.get('message')}", parse_mode="HTML",
                                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="list_backups")]]))
        await callback.answer()
    except Exception as e:
        logger.exception(f"Ошибка в backup_restore_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "backup_stats")
async def backup_stats_handler(callback: CallbackQuery) -> None:
    """Показать статистику бэкапов"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        bm = BackupManager()
        stats = await bm.get_backup_stats()

        nb = stats.get('newest_backup')
        nb_str = f"{nb['name']} ({nb['size_mb']} MB) — {nb['created'].strftime('%d.%m.%Y %H:%M')}" if nb else "Нет"

        text = f"""
📊 <b>Статистика бэкапов</b>

• Всего бэкапов: {stats.get('total_backups', 0)}
• Общий размер: {stats.get('total_size_mb', 0)} MB
• Средний размер: {stats.get('average_size_mb', 0)} MB
• Последний бэкап: {nb_str}
"""
        await callback.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")]]), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.exception(f"Ошибка в backup_stats_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "cleanup_backups")
async def cleanup_backups_handler(callback: CallbackQuery) -> None:
    """Ручная очистка старых бэкапов (по заданным правилам)"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        bm = BackupManager()
        res = await bm.clean_old_backups(days=7)
        if res.get('deleted_count', 0) > 0:
            freed_mb = round(res['freed_space']/1024/1024, 2)
            await callback.message.edit_text(text=f"🧹 Очистка завершена.\nУдалено: {res['deleted_count']} файлов\nОсвобождено: {freed_mb} MB", parse_mode="HTML",
                                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_backups")]]))
        else:
            await callback.answer("Нет старых бэкапов для удаления.")
    except Exception as e:
        logger.exception(f"Ошибка в cleanup_backups_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)