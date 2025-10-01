"""
Обработчики callback запросов
Дополнительные callback'и, не входящие в основные модули
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from database import PostOperations, UserOperations, PaymentOperations
from utils.helpers import MessageFormatter, format_user_info
from utils.states import PostCreation
from config import settings, PaymentStatus

logger = logging.getLogger(__name__)
router = Router()


async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """
    Безопасный ответ на callback, игнорирующий устаревшие запросы
    """
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            # Игнорируем устаревшие callback'и
            logger.debug(f"Игнорируем устаревший callback от {callback.from_user.id}: {callback.data}")
            pass
        else:
            # Перебрасываем другие ошибки
            raise e
    except Exception as e:
        logger.error(f"Ошибка в safe_callback_answer: {e}")


@router.callback_query(F.data.startswith("view_post:"))
async def view_post_callback(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра деталей поста
    """
    try:
        post_id = int(callback.data.split(":")[1])

        # Получаем данные поста
        post = await PostOperations.get_post(post_id)
        if not post:
            await safe_callback_answer(callback, "❌ Пост не найден", show_alert=True)
            return

        # Проверяем принадлежность поста пользователю
        if post['user_id'] != callback.from_user.id:
            await safe_callback_answer(callback, "❌ Это не ваш пост", show_alert=True)
            return

        # Форматируем информацию о посте
        post_info = MessageFormatter.format_post_info(post)

        status_text = {
            'draft': '📝 Черновик',
            'published': '✅ Опубликован',
            'archived': '📦 Архивирован'
        }.get(post['status'], '❓ Неизвестен')

        text = f"""
📄 <b>Детали поста</b>

{post_info}

📊 <b>Информация:</b>
• Статус: {status_text}
• ID поста: {post_id}
"""

        if post['message_id']:
            text += f"\n• ID сообщения: {post['message_id']}"
            text += f"\n🔗 Ссылка: https://t.me/rc_exchng/{post['message_id']}"

        from keyboards.inline import NavigationKeyboards
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=NavigationKeyboards.get_back_to_main_menu(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except TelegramBadRequest as e:
            if "query is too old" in str(e):
                # Если сообщение устарело, отправляем новое
                await callback.message.answer(
                    text=text,
                    reply_markup=NavigationKeyboards.get_back_to_main_menu(),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            else:
                raise e

        await safe_callback_answer(callback)

    except ValueError:
        await safe_callback_answer(callback, "❌ Неверный ID поста", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в view_post_callback: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("user_profile:"))
async def user_profile_callback(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра профиля пользователя (только для админа)
    """
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await safe_callback_answer(callback, "❌ Доступ запрещен", show_alert=True)
            return

        # Получаем payment_id из callback_data
        payment_id = int(callback.data.split(":")[1])

        # Получаем платеж, чтобы найти пользователя
        payment = await PaymentOperations.get_payment(payment_id)

        if not payment:
            await safe_callback_answer(callback, "❌ Платеж не найден", show_alert=True)
            return

        # Получаем данные пользователя
        user = await UserOperations.get_user(payment['user_id'])
        if not user:
            await safe_callback_answer(callback, "❌ Пользователь не найден", show_alert=True)
            return

        # Получаем статистику пользователя
        user_posts = await PostOperations.get_user_posts(payment['user_id'])
        user_payments = await PaymentOperations.get_user_payments(payment['user_id'])

        from utils.helpers import format_datetime

        text = f"""
👤 <b>Профиль пользователя</b>

<b>📋 Основная информация:</b>
{format_user_info(user)}

<b>📊 Статистика:</b>
• ID: {user['user_id']}
• Регистрация: {format_datetime(user.get('reg_date'))}
• Телефон: {user.get('phone', 'Не указан')}
• Постов создано: {len(user_posts)}
• Платежей: {len(user_payments)}
• Баланс: {user.get('balance', 0)} ₽

<b>📈 Активность:</b>
• Последний пост: {format_datetime(user_posts[0].get('created_at')) if user_posts else 'Нет постов'}
• Последний платеж: {format_datetime(user_payments[0].get('created_at')) if user_payments else 'Нет платежей'}

<b>🔒 Статус:</b>
• Заблокирован: {'Да' if user.get('is_blocked', False) else 'Нет'}
"""

        from keyboards.inline import AdminKeyboards
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=AdminKeyboards.get_admin_menu(),
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "query is too old" in str(e):
                await callback.message.answer(
                    text=text,
                    reply_markup=AdminKeyboards.get_admin_menu(),
                    parse_mode="HTML"
                )
            else:
                raise e

        await safe_callback_answer(callback)

    except ValueError:
        await safe_callback_answer(callback, "❌ Неверный ID платежа", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в user_profile_callback: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("continue_post:"))
async def continue_post_creation(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Продолжение создания поста после подтверждения платежа
    """
    try:
        payment_id = int(callback.data.split(":")[1])

        # Получаем данные платежа
        payment = await PaymentOperations.get_payment(payment_id)

        if not payment:
            await safe_callback_answer(callback, "❌ Платеж не найден", show_alert=True)
            return

        if payment['user_id'] != callback.from_user.id:
            await safe_callback_answer(callback, "❌ Это не ваш платеж", show_alert=True)
            return

        if payment['status'] != PaymentStatus.CONFIRMED:
            await safe_callback_answer(callback, "❌ Платеж не подтвержден", show_alert=True)
            return

        # Определяем тип поста по сумме
        post_type = 'regular'
        if payment['amount'] == settings.PINNED_POST_PRICE:
            post_type = 'pinned'
        elif payment['amount'] == settings.REGULAR_POST_PRICE:
            post_type = 'regular'

        # Устанавливаем состояние и данные для создания поста
        await state.set_state(PostCreation.waiting_photos)
        await state.update_data(
            payment_id=payment_id,
            post_type=post_type,
            price=payment['amount'],
            photos=[]
        )

        post_type_name = "Закрепленный" if post_type == 'pinned' else "Обычный"

        text = f"""
📝 <b>Создание поста</b>

Платеж №{payment_id} подтвержден!
Тип поста: <b>{post_type_name}</b>

📸 <b>Шаг 1: Загрузите фотографии</b>

Отправьте от {settings.MIN_PHOTOS} до {settings.MAX_PHOTOS} фотографий вашего товара.

💡 <b>Советы:</b>
• Хорошее освещение
• Разные ракурсы
• Четкие снимки
• Покажите дефекты (если есть)

<b>Загрузите первую фотографию 📸</b>
"""

        try:
            await callback.message.edit_text(text=text, parse_mode="HTML")
        except TelegramBadRequest as e:
            if "query is too old" in str(e):
                await callback.message.answer(text=text, parse_mode="HTML")
            else:
                raise e

        await safe_callback_answer(callback, "📝 Начинаем создание поста!")

    except ValueError:
        await safe_callback_answer(callback, "❌ Неверный ID платежа", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в continue_post_creation: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


# Обработчик для всех неопознанных callback'ов
@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    """
    Обработчик неизвестных callback запросов
    """
    try:
        logger.warning(f"Неизвестный callback от {callback.from_user.id}: {callback.data}")

        # Проверяем, не устаревший ли это callback
        try:
            await callback.answer(
                "❓ Это старая кнопка. Воспользуйтесь командой /start для обновления",
                show_alert=True
            )
        except TelegramBadRequest as e:
            if "query is too old" in str(e) or "query ID is invalid" in str(e):
                logger.debug(f"Игнорируем устаревший callback: {callback.data}")
                return
            else:
                # Если это другая ошибка, попробуем отправить новое сообщение
                try:
                    await callback.message.answer(
                        "❓ Это старая кнопка. Воспользуйтесь командой /start для обновления"
                    )
                except:
                    # Если и это не работает, просто логируем
                    logger.error(f"Не удалось ответить на callback {callback.data}")

    except Exception as e:
        logger.error(f"Ошибка в unknown_callback: {e}")
