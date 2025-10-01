"""\
Обработчик команды /start и главного меню
Регистрация пользователей и отображение основного интерфейса
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from database import UserOperations, PaymentOperations, AdminOperations
from keyboards.inline import MainKeyboards, NavigationKeyboards, AdminKeyboards, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.reply import ReplyKeyboards
from utils.helpers import UserHelper
from config import settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start с проверкой принятия оферты"""
    try:
        await state.clear()

        user = message.from_user
        user_data = UserHelper.extract_user_data(user)
        is_admin = user.id == settings.ADMIN_ID

        # Регистрируем или обновляем пользователя
        success = await UserOperations.create_user(
            user_id=user_data['user_id'],
            username=user_data['username'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name']
        )

        if success:
            logger.info(f"Пользователь {user.id} зарегистрирован/обновлен")

        # Проверяем, принял ли пользователь оферту
        has_accepted = await UserOperations.has_accepted_offer(user.id)

        if not has_accepted:
            offer_text = f"""
👋 <b>Добро пожаловать, {user.first_name or "друг"}!</b>

Это бот Richmond Market для размещения объявлений о продаже в канале @richmondmarket.

<b>Кратко о сервисе:</b>
- Размещение объявлений в канале
- Автоматическая обработка платежей
- Техническая поддержка 24/7
- Безопасные сделки

<b>📋 Для использования бота необходимо ознакомиться с условиями:</b>
"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📖 Читать публичную оферту",
                    url="https://telegra.ph/Publichnaya-Oferta-RICHMOND-MARKET-09-27"
                )],
                [InlineKeyboardButton(
                    text="✅ Я ознакомился и принимаю условия",
                    callback_data="accept_offer"
                )]
            ])

            await message.answer(
                text=offer_text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            welcome_text = f"""
🎉 <b>Добро пожаловать в Richmond Market!</b>

Привет, {user.first_name or "друг"}! 👋

<b>💰 Цены:</b>
- Обычный пост: 200₽
- Закрепленный пост: 1000₽

<b>🔥 Преимущества:</b>
✅ Автоматическая оплата
✅ Электронные чеки
✅ Большая аудитория
✅ Поддержка 24/7

Готов разместить пост? 🚀
"""

            await message.answer(
                text=welcome_text,
                reply_markup=MainKeyboards.get_main_menu(user.id, settings.ADMIN_ID),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            # Отправляем reply-клавиатуру
            await message.answer(
                text="Используйте кнопку ниже для быстрого доступа:",
                reply_markup=ReplyKeyboards.get_start_keyboard(is_admin)
            )

    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже.",
            reply_markup=NavigationKeyboards.get_back_to_main_menu()
        )

@router.message(F.text == "🚀 Начать работу")
async def start_work_button(message: Message) -> None:
    """Обработчик кнопки 'Начать работу'"""
    try:
        await message.answer(
            text="🏠 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=MainKeyboards.get_main_menu(message.from_user.id, settings.ADMIN_ID),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в start_work_button: {e}")


@router.message(F.text == "👑 Админ-панель")
async def admin_panel_button(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Админ-панель'"""
    try:
        if message.from_user.id != settings.ADMIN_ID:
            await message.answer("❌ У вас нет прав доступа")
            return

        await state.clear()

        stats = await AdminOperations.get_stats()
        pending_payments = await PaymentOperations.get_pending_payments()

        text = f"""
👑 <b>Панель администратора</b>

📊 <b>Быстрая статистика:</b>
- Пользователей: {stats.get('users', {}).get('total', 0)}
- Постов: {stats.get('posts', {}).get('total', 0)}
- Платежей на проверке: {len(pending_payments)}
- Доход: {stats.get('payments', {}).get('revenue', 0)} ₽

Выберите действие: 👇
"""
        await message.answer(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_panel_button: {e}")

@router.callback_query(F.data == "accept_offer")
async def accept_offer(callback: CallbackQuery) -> None:
    """Принятие публичной оферты"""
    try:
        user_id = callback.from_user.id

        # Сохраняем согласие пользователя в базе данных
        success = await UserOperations.update_offer_accepted(user_id)

        if success:
            welcome_text = f"""
✅ <b>Спасибо за принятие условий!</b>

🎉 <b>Добро пожаловать в Richmond Market!</b>

Привет, {callback.from_user.first_name or "друг"}! 👋

Этот бот поможет тебе разместить объявление о продаже в нашем канале <a href="https://t.me/richmondmarket">@richmondmarket</a>.

<b>📋 Как это работает:</b>
1️⃣ Выбираешь тип поста (обычный или закрепленный)
2️⃣ Оплачиваешь размещение через безопасную платежную систему
3️⃣ Загружаешь фотографии и описание товара
4️⃣ Твой пост появляется в канале!

<b>💰 Цены:</b>
• Обычный пост: 200₽
• Закрепленный пост: 1000₽

<b>🔥 Преимущества:</b>
✅ Автоматическая оплата
✅ Электронные чеки
✅ Большая аудитория
✅ Поддержка 24/7

Готов разместить свой первый пост? 🚀
"""

            await callback.message.edit_text(
                text=welcome_text,
                reply_markup=MainKeyboards.get_main_menu(user_id, settings.ADMIN_ID),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            await callback.answer("✅ Условия приняты!")
        else:
            await callback.answer("❌ Ошибка сохранения. Попробуйте еще раз.", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в accept_offer: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик возврата в главное меню

    Args:
        callback: Callback запрос
        state: Состояние FSM
    """
    try:
        # Очищаем состояние
        await state.clear()

        main_menu_text = f"""\
🏠 <b>Главное меню</b>

Выберите действие из меню ниже:

📝 <b>Разместить пост</b> - создать новое объявление
📋 <b>Мои посты</b> - просмотреть свои объявления
💳 <b>История платежей</b> - посмотреть все платежи
ℹ️ <b>Информация</b> - помощь и контакты

Что хотите сделать? 👇\
"""

        await callback.message.edit_text(
            text=main_menu_text,
            reply_markup=MainKeyboards.get_main_menu(callback.from_user.id, settings.ADMIN_ID),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в back_to_main_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "info")
async def info_handler(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Информация" """
    try:
        info_text = f"""\
ℹ️ <b>Информация о боте</b>

<b>🤖 Richmond Market Bot</b>
Бот для размещения платных объявлений в канале @richmondmarket

<b>💰 Тарифы:</b>
- Обычный пост: {settings.REGULAR_POST_PRICE}₽
- Закрепленный пост: {settings.PINNED_POST_PRICE}₽

<b>📋 Требования к посту:</b>
- Минимум {settings.MIN_PHOTOS} фотографии
- Максимум {settings.MAX_PHOTOS} фотографий
- Подробное описание товара
- Контактная информация

<b>💳 Способы оплаты:</b>
- СБП (Система быстрых платежей)

<b>⏱ Время размещения:</b>
После подтверждения оплаты администратором ваш пост будет опубликован в течение 5-10 минут.

<b>📞 Поддержка:</b>
По всем вопросам обращайтесь к @balykoal

<b>📋 Правила:</b>
- Запрещена продажа запрещенных товаров
- Фотографии должны соответствовать описанию
- Один товар - один пост
- Дубли постов удаляются

Удачных продаж! 🍀\
"""

        # Создаем клавиатуру с кнопкой оферты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📖 Публичная оферта",
                url="https://telegra.ph/Publichnaya-Oferta-RICHMOND-MARKET-09-27"
            )],
            [InlineKeyboardButton(
                text="◀️ Главное меню",
                callback_data="back_to_main"
            )]
        ])

        await callback.message.edit_text(
            text=info_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в info_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "my_posts")
async def my_posts_handler(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра постов пользователя

    Args:
        callback: Callback запрос
    """
    try:
        user_id = callback.from_user.id

        # Получаем посты пользователя
        from database import PostOperations
        posts = await PostOperations.get_user_posts(user_id)

        if not posts:
            text = """\
📋 <b>Мои посты</b>

У вас пока нет созданных постов.

Хотите создать свой первый пост? Нажмите "Разместить пост" в главном меню! 🚀\
"""
        else:
            text = f"""\
📋 <b>Мои посты</b>

Всего постов: {len(posts)}

Выберите пост для просмотра деталей:\
"""

        from keyboards.inline import PostKeyboards
        await callback.message.edit_text(
            text=text,
            reply_markup=PostKeyboards.get_my_posts_menu(posts),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в my_posts_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "my_payments")
async def my_payments_handler(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра истории платежей

    Args:
        callback: Callback запрос
    """
    try:
        user_id = callback.from_user.id

        # Получаем платежи пользователя
        from database import PaymentOperations
        payments = await PaymentOperations.get_user_payments(user_id)

        if not payments:
            text = """\
💳 <b>История платежей</b>

У вас пока нет платежей.

Создайте свой первый пост, чтобы увидеть здесь историю! 💪\
"""
        else:
            text = f"""\
💳 <b>История платежей</b>

Всего платежей: {len(payments)}

<b>Последние платежи:</b>\
"""

            from utils.helpers import format_price, format_datetime
            for payment in payments[:5]:  # Показываем последние 5
                status_emoji = {
                    'pending': '⏳',
                    'checking': '🔍',
                    'confirmed': '✅',
                    'rejected': '❌',
                    'expired': '⏰'
                }.get(payment['status'], '❓')

                method_text = "СБП" if payment['method'] == 'sbp' else "Крипта"

                text += f"""
{status_emoji} {format_price(payment['amount'])} ₽ ({method_text})
{format_datetime(payment['created_at'])}\
"""

        await callback.message.edit_text(
            text=text,
            reply_markup=NavigationKeyboards.get_back_to_main_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в my_payments_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "close_menu")
async def close_menu_handler(callback: CallbackQuery) -> None:
    """
    Обработчик закрытия меню

    Args:
        callback: Callback запрос
    """
    try:
        await callback.message.delete()
        await callback.answer("Меню закрыто")

    except Exception as e:
        logger.error(f"Ошибка в close_menu_handler: {e}")
        await callback.answer()


@router.callback_query(F.data.in_(["no_posts", "no_pending_payments", "current_page"]))
async def dummy_callbacks_handler(callback: CallbackQuery) -> None:
    """
    Обработчик пустых callback'ов (заглушки)

    Args:
        callback: Callback запрос
    """
    await callback.answer()


@router.callback_query(F.data == "admin_panel_mode")
async def admin_panel_mode(callback: CallbackQuery, state: FSMContext):
    """Переход в админ-панель"""
    try:
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ У вас нет прав доступа к админ-панели", show_alert=True)
            return

        await state.clear()

        # Получаем базовую статистику
        try:
            stats = await AdminOperations.get_stats()
            pending_payments = await PaymentOperations.get_pending_payments()
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            stats = {'users': {'total': 0}, 'posts': {'total': 0}, 'payments': {'revenue': 0}}
            pending_payments = []

        text = f"""\
👑 <b>Панель администратора</b>

📊 <b>Быстрая статистика:</b>
• Пользователей: {stats.get('users', {}).get('total', 0)}
• Постов: {stats.get('posts', {}).get('total', 0)}
• Платежей на проверке: {len(pending_payments)}
• Доход: {stats.get('payments', {}).get('revenue', 0)} ₽

Выберите действие: 👇\
"""
        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.get_admin_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_panel_mode: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# Обработчик для всех остальных сообщений в обычном состоянии
@router.message(StateFilter(None))
async def default_message_handler(message: Message) -> None:
    """
    Обработчик сообщений по умолчанию

    Args:
        message: Сообщение пользователя
    """
    try:
        # Проверяем, является ли пользователь админом
        if message.from_user.id == settings.ADMIN_ID:
            # Для админа показываем админ-панель
            from keyboards.inline import AdminKeyboards
            await message.answer(
                "👑 <b>Панель администратора</b>\n\nВыберите действие:",
                reply_markup=AdminKeyboards.get_admin_menu(),
                parse_mode="HTML"
            )
        else:
            # Для обычного пользователя - главное меню
            await message.answer(
                "👋 Используйте кнопки меню для навигации",
                reply_markup=MainKeyboards.get_main_menu(message.from_user.id, settings.ADMIN_ID)
            )

    except Exception as e:
        logger.error(f"Ошибка в default_message_handler: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте использовать /start",
            reply_markup=MainKeyboards.get_main_menu(message.from_user.id, settings.ADMIN_ID)
        )