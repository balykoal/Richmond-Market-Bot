"""
Обработчики создания поста
FSM для сбора данных о товаре и публикации
"""

import logging
from datetime import datetime
import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from database import PostOperations, UserOperations, PaymentOperations
from keyboards.inline import PostKeyboards, MainKeyboards
from utils.states import PostCreation
from utils.validators import DataValidators
from utils.helpers import MediaHelper, MessageFormatter, send_notification_to_admin, format_price, PriceHelper
from services.post_service import PostService
from config import settings, ItemCondition, PostType

logger = logging.getLogger(__name__)
router = Router()


async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """Безопасный ответ на callback с обработкой устаревших запросов"""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            logger.debug(f"Игнорируем устаревший callback от {callback.from_user.id}: {callback.data}")
        else:
            raise e
    except Exception as e:
        logger.error(f"Ошибка в safe_callback_answer: {e}")


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасное редактирование сообщения"""
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "query is too old" in str(e) or "message is not modified" in str(e):
            try:
                await callback.message.answer(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
            except:
                pass
        else:
            raise e


@router.message(F.photo, PostCreation.waiting_photos)
async def receive_photo(message: Message, state: FSMContext):
    """Получение фотографий от пользователя с поддержкой медиагрупп"""
    try:
        data = await state.get_data()
        photos = data.get('photos', [])
        media_group_id = message.media_group_id
        current_media_group = data.get('media_group_id')

        # Получаем лучшее качество фото
        best_photo = MediaHelper.get_largest_photo(message.photo)
        photos.append(best_photo.file_id)

        # Сохраняем фото в состояние
        await state.update_data(photos=photos)

        if media_group_id:
            # Если это новая медиагруппа или первое фото из группы
            if current_media_group != media_group_id:
                await state.update_data(
                    media_group_id=media_group_id,
                    processing_media_group=True
                )

                # Ждем остальные фото из группы
                await asyncio.sleep(1.0)  # Увеличиваем время ожидания

                # Получаем финальные данные после ожидания
                final_data = await state.get_data()
                final_photos = final_data.get('photos', [])

                # Проверяем, что мы все еще обрабатываем ту же группу
                if final_data.get('media_group_id') == media_group_id:
                    await process_photos_complete(message, state, len(final_photos))
            # Если это продолжение той же группы - просто добавляем фото и ждем

        else:
            # Одиночное фото - обрабатываем сразу
            await process_photos_complete(message, state, 1)

    except Exception as e:
        logger.error(f"Ошибка в receive_photo: {e}")
        await message.answer("❌ Ошибка обработки фотографии. Попробуйте еще раз.")


async def process_photos_complete(message: Message, state: FSMContext, new_photos_count: int):
    """Обработка завершенной загрузки фотографий"""
    try:
        data = await state.get_data()
        photos = data.get('photos', [])
        total_photos = len(photos)

        # Сбрасываем флаги медиагруппы
        await state.update_data(
            processing_media_group=False,
            media_group_id=None
        )

        if total_photos >= settings.MAX_PHOTOS:
            # Максимум достигнут
            if data.get('is_editing'):
                await back_to_preview_from_message(message, state)
            else:
                await state.set_state(PostCreation.waiting_title)
                text = f"""
📸 <b>Фотографии загружены!</b>

Загружено: {total_photos} из {settings.MAX_PHOTOS} фото

Теперь введите название вашего товара.

💡 <b>Советы:</b>
• Будьте конкретными
• Укажите бренд и модель
• Избегайте лишних символов

<b>Введите название товара:</b>
"""
                await message.answer(text, parse_mode="HTML")

        elif total_photos >= settings.MIN_PHOTOS:
            # Минимум достигнут, можно продолжить
            text = f"""
✅ <b>Отлично! Фотографии готовы</b>

Загружено: {total_photos} фото

Вы можете загрузить еще фото или перейти к следующему шагу.
"""
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➡️ Далее", callback_data="photos_next_step")
            ]])
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            # Нужно еще фото
            remaining = settings.MIN_PHOTOS - total_photos
            text = f"""
📸 <b>Фото добавлено!</b>

Загружено: {total_photos} из {settings.MIN_PHOTOS} (минимум) фото

Загрузите еще {remaining} фото для продолжения.
"""
            await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в process_photos_complete: {e}")
        await message.answer("❌ Ошибка обработки фотографий.")


@router.callback_query(F.data == "photos_next_step", PostCreation.waiting_photos)
async def photos_next_step_handler(callback: CallbackQuery, state: FSMContext):
    """Переход к следующему шагу после загрузки фото"""
    try:
        data = await state.get_data()
        photos = data.get('photos', [])

        if len(photos) < settings.MIN_PHOTOS:
            await safe_callback_answer(callback, f"❌ Нужно загрузить минимум {settings.MIN_PHOTOS} фотографии", show_alert=True)
            return

        if data.get('is_editing'):
            await back_to_preview_handler(callback, state)
            return

        await state.set_state(PostCreation.waiting_title)
        text = f"""
✅ <b>Отлично! Фотографии готовы</b>

Загружено: {len(photos)} фото

Теперь введите название вашего товара.

💡 <b>Советы для названия:</b>
• Будьте конкретными
• Укажите бренд и модель
• Укажите основные характеристики

<b>Введите название товара:</b>
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в photos_next_step_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("post_type:"), PostCreation.choosing_post_type)
async def post_type_selected(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа поста"""
    try:
        post_type = callback.data.split(":")[1]
        is_admin = callback.from_user.id == settings.ADMIN_ID

        await state.update_data(post_type=post_type)
        price = PriceHelper.get_post_price(post_type)
        post_type_name = "Закрепленный" if post_type == PostType.PINNED else "Обычный"

        if is_admin:
            # Для админа автоматически создаем подтвержденный платеж
            payment_id = await PaymentOperations.create_payment(
                user_id=callback.from_user.id,
                amount=price,
                method="admin_auto",
                currency="RUB"
            )

            if payment_id:
                await PaymentOperations.confirm_payment(payment_id, callback.from_user.id)
                await state.update_data(payment_id=payment_id, price=price)
                await state.set_state(PostCreation.waiting_photos)

                text = f"""
👑 <b>Администратор: платеж автоматически подтвержден!</b>

Тип поста: <b>{post_type_name}</b>
Стоимость: <b>{format_price(price)} ₽</b>
Платеж №{payment_id} подтвержден автоматически.

Теперь приступим к созданию поста!

📸 <b>Шаг 1: Загрузите фотографии</b>

Отправьте от {settings.MIN_PHOTOS} до {settings.MAX_PHOTOS} фотографий вашего товара.

Загрузите первую фотографию:
"""
                await safe_edit_message(callback, text)
                await safe_callback_answer(callback, "👑 Платеж подтвержден автоматически!")
                return

        # Для обычных пользователей
        await state.set_state(PostCreation.choosing_payment_method)
        text = f"""
💳 <b>Выбор способа оплаты</b>

Вы выбрали: <b>{post_type_name} пост</b>
Стоимость: <b>{format_price(price)} ₽</b>

Выберите удобный способ оплаты:

🏦 <b>СБП (Система быстрых платежей)</b>
• Оплата с банковской карты
• Мгновенный перевод
• Без комиссии
"""
        await safe_edit_message(callback, text, MainKeyboards.get_payment_method_menu())
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в post_type_selected: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.message(F.text, PostCreation.waiting_title)
async def receive_title(message: Message, state: FSMContext):
    """Получение названия товара"""
    try:
        title = message.text.strip()

        validation = DataValidators.validate_title(title)
        if not validation.is_valid:
            await message.answer(f"❌ {validation.error_message}")
            return

        await state.update_data(title=title)
        data = await state.get_data()

        if data.get('is_editing'):
            await message.answer("✅ Название успешно обновлено!")
            await back_to_preview_from_message(message, state)
            return

        await state.set_state(PostCreation.waiting_condition)
        text = f"""
✅ <b>Название сохранено!</b>

<b>"{title}"</b>

Теперь укажите состояние товара:

✨ <b>Новое</b> - товар не использовался, в оригинальной упаковке
🔄 <b>Б/у</b> - товар был в использовании

Выберите состояние товара:
"""
        await message.answer(text, reply_markup=PostKeyboards.get_item_condition_menu(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в receive_title: {e}")
        await message.answer("❌ Ошибка сохранения названия. Попробуйте еще раз.")


@router.callback_query(F.data.startswith("condition:"), PostCreation.waiting_condition)
async def condition_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор состояния товара"""
    try:
        condition = callback.data.split(":")[1]
        await state.update_data(condition=condition)

        data = await state.get_data()
        if data.get('is_editing'):
            await back_to_preview_handler(callback, state)
            return

        await state.set_state(PostCreation.waiting_description)
        condition_text = "✨ Новое" if condition == ItemCondition.NEW else "🔄 Б/у"

        text = f"""
✅ <b>Состояние товара выбрано!</b>

Состояние: <b>{condition_text}</b>

Теперь напишите подробное описание товара.

💡 <b>Что указать в описании:</b>
• Состояние
• Комплектность
• Дефекты (если есть)

<b>Минимум:</b> 20 символов
<b>Максимум:</b> 1000 символов

<b>Введите описание товара:</b>
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в condition_selected: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.message(F.text, PostCreation.waiting_description)
async def receive_description(message: Message, state: FSMContext):
    """Получение описания товара"""
    try:
        description = message.text.strip()

        validation = DataValidators.validate_description(description)
        if not validation.is_valid:
            await message.answer(f"❌ {validation.error_message}")
            return

        await state.update_data(description=description)
        data = await state.get_data()

        if data.get('is_editing'):
            await message.answer("✅ Описание успешно изменено!")
            await back_to_preview_from_message(message, state)
            return

        await state.set_state(PostCreation.waiting_price)
        text = """
✅ <b>Описание сохранено!</b>

Теперь укажите цену товара.

💡 <b>Как указать цену:</b>
• Только цифры и точку/запятую для копеек
• Примеры: 15000, 15000.50, 25,5
• Цена должна быть больше 0

<b>Введите цену в рублях:</b>
"""
        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в receive_description: {e}")
        await message.answer("❌ Ошибка сохранения описания. Попробуйте еще раз.")


@router.message(F.text, PostCreation.waiting_price)
async def receive_price(message: Message, state: FSMContext):
    """Получение цены товара"""
    try:
        validation, price = DataValidators.validate_price(message.text)
        if not validation.is_valid:
            await message.answer(f"❌ {validation.error_message}")
            return

        await state.update_data(price=price)
        data = await state.get_data()

        if data.get('is_editing'):
            await message.answer("✅ Цена успешно изменена!")
            await back_to_preview_from_message(message, state)
            return

        await state.set_state(PostCreation.waiting_contact)
        text = f"""
✅ <b>Цена сохранена!</b>

Цена: <b>{format_price(price)} ₽</b>

Теперь укажите контактную информацию.

💡 <b>Что можно указать:</b>
• Номер телефона
• Имя Telegram (@username)

<b>Пример:</b>
+7 (999) 123-45-67
@username

<b>Введите контактную информацию:</b>
"""
        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в receive_price: {e}")
        await message.answer("❌ Ошибка сохранения цены. Попробуйте еще раз.")


@router.message(F.text, PostCreation.waiting_contact)
async def receive_contact(message: Message, state: FSMContext):
    """Получение контактной информации"""
    try:
        contact_info = message.text.strip()

        validation = DataValidators.validate_contact_info(contact_info)
        if not validation.is_valid:
            await message.answer(f"❌ {validation.error_message}")
            return

        await state.update_data(contact_info=contact_info)
        data = await state.get_data()

        if data.get('is_editing'):
            await back_to_preview_from_message(message, state)
            return

        # Переходим к подтверждению
        await show_post_preview(message, state, data)

    except Exception as e:
        logger.error(f"Ошибка в receive_contact: {e}")
        await message.answer("❌ Ошибка сохранения контактов. Попробуйте еще раз.")


async def show_post_preview(message: Message, state: FSMContext, data: dict):
    """Показать предварительный просмотр поста"""
    try:
        await state.set_state(PostCreation.confirming_post)

        # Создаем превью поста
        post_preview = MessageFormatter.format_post_info({
            'title': data['title'],
            'condition': data['condition'],
            'description': data['description'],
            'price': data['price'],
            'contact_info': data['contact_info'],
            'post_type': data['post_type'],
            'created_at': message.date
        })

        photos = data.get('photos', [])

        text = f"""
✅ <b>Все данные собраны!</b>

<b>Предварительный просмотр поста:</b>

{post_preview}

Все верно? Опубликовать пост?
"""

        if photos and len(photos) > 0:
            # Показываем с фотографиями
            media = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=file_id))

            await message.answer_media_group(media=media)
            await message.answer(
                "Выберите действие:",
                reply_markup=PostKeyboards.get_post_confirmation_menu()
            )
        else:
            # Только текст
            await message.answer(
                text,
                reply_markup=PostKeyboards.get_post_confirmation_menu(),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка в show_post_preview: {e}")
        await message.answer("❌ Ошибка формирования превью.")


@router.callback_query(F.data == "confirm_post", PostCreation.confirming_post)
async def confirm_post(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и публикация поста"""
    try:
        data = await state.get_data()
        user_id = callback.from_user.id

        # Создаем пост в базе данных
        post_id = await PostOperations.create_post(
            user_id=user_id,
            photos=data['photos'],
            title=data['title'],
            condition=data['condition'],
            description=data['description'],
            price=data['price'],
            contact_info=data['contact_info'],
            post_type=data['post_type']
        )

        if not post_id:
            await safe_callback_answer(callback, "❌ Ошибка создания поста", show_alert=True)
            return

        # Публикуем пост в канале
        post_service = PostService(callback.bot)
        success, message_id = await post_service.publish_post(post_id)

        if success:
            await PostOperations.publish_post(post_id, message_id)
            await UserOperations.increment_post_count(user_id)
            await state.clear()

            text = f"""
🎉 <b>Пост успешно опубликован!</b>

✅ Ваш пост размещен в канале @richmondmarket
📊 ID поста: {post_id}
🔗 Ссылка: https://t.me/richmond_market/{message_id}

<b>Что дальше:</b>
• Ваш пост увидят подписчики канала
• Покупатели смогут связаться с вами
• Следите за сообщениями!

Спасибо за использование нашего сервиса!

Хотите разместить еще один пост?
"""
            await safe_edit_message(
                callback,
                text,
                MainKeyboards.get_main_menu(callback.from_user.id, settings.ADMIN_ID)
            )

            # Уведомляем админа
            admin_text = f"""
🎉 <b>Новый пост опубликован</b>

Пост №{post_id}
Пользователь: {callback.from_user.first_name or 'Без имени'} (@{callback.from_user.username or 'без username'})
Тип: {"Закрепленный" if data['post_type'] == 'pinned' else "Обычный"}
Товар: {data['title']}
Цена: {data['price']} ₽
"""
            await send_notification_to_admin(callback.bot, admin_text)
        else:
            await safe_callback_answer(callback, "❌ Ошибка публикации поста", show_alert=True)

        await safe_callback_answer(callback, "🎉 Пост опубликован!")

    except Exception as e:
        logger.error(f"Ошибка в confirm_post: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при публикации", show_alert=True)


@router.callback_query(F.data == "cancel_post", PostCreation.confirming_post)
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    """Отмена создания поста"""
    try:
        await state.clear()
        text = """
❌ <b>Создание поста отменено</b>

Все введенные данные были удалены.

Если захотите создать пост заново, нажмите "Разместить пост" в главном меню!
"""
        await safe_edit_message(
            callback,
            text,
            MainKeyboards.get_main_menu(callback.from_user.id, settings.ADMIN_ID)
        )
        await safe_callback_answer(callback, "❌ Создание поста отменено")

    except Exception as e:
        logger.error(f"Ошибка в cancel_post: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "edit_post", PostCreation.confirming_post)
async def edit_post_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки редактирования поста"""
    try:
        data = await state.get_data()
        await state.update_data(is_editing=True)

        current_photos_count = len(data.get('photos', []))
        current_title = data.get('title', 'Не указано')

        text = f"""
✏️ <b>Редактирование поста</b>

📊 <b>Текущие данные:</b>
• 📸 Фото: {current_photos_count} шт.
• 📝 Название: {current_title[:30]}...

Выберите, что хотите изменить:
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📸 Фото", callback_data="edit_photos"),
                InlineKeyboardButton(text="📝 Название", callback_data="edit_title")
            ],
            [
                InlineKeyboardButton(text="🏷 Состояние", callback_data="edit_condition"),
                InlineKeyboardButton(text="📄 Описание", callback_data="edit_description")
            ],
            [
                InlineKeyboardButton(text="💰 Цена", callback_data="edit_price"),
                InlineKeyboardButton(text="📞 Контакты", callback_data="edit_contact")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_preview")
            ]
        ])

        await safe_edit_message(callback, text, keyboard)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в edit_post_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "edit_title", PostCreation.confirming_post)
async def edit_title_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование названия"""
    try:
        current_data = await state.get_data()
        current_data['is_editing'] = True
        await state.set_state(PostCreation.waiting_title)
        await state.set_data(current_data)

        current_title = current_data.get('title', 'Не указано')
        text = f"""
📝 <b>Редактирование названия</b>

Текущее название: <b>"{current_title}"</b>

Введите новое название товара:
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback, "✏️ Введите новое название")

    except Exception as e:
        logger.error(f"Ошибка в edit_title_handler: {e}")
        await safe_callback_answer(callback, "❌ Ошибка при редактировании названия", show_alert=True)


@router.callback_query(F.data == "edit_description", PostCreation.confirming_post)
async def edit_description_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование описания"""
    try:
        current_data = await state.get_data()
        current_data['is_editing'] = True
        await state.set_state(PostCreation.waiting_description)
        await state.set_data(current_data)

        current_description = current_data.get('description', '')
        text = f"""
📄 <b>Редактирование описания</b>

Текущее описание:
"{current_description}"

Введите новое описание товара:
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в edit_description_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "edit_price", PostCreation.confirming_post)
async def edit_price_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование цены"""
    try:
        current_data = await state.get_data()
        current_data['is_editing'] = True
        await state.set_state(PostCreation.waiting_price)
        await state.set_data(current_data)

        current_price = current_data.get('price', 0)
        text = f"""
💰 <b>Редактирование цены</b>

Текущая цена: <b>{format_price(current_price)} ₽</b>

Введите новую цену товара:
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в edit_price_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "edit_condition", PostCreation.confirming_post)
async def edit_condition_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование состояния товара"""
    try:
        current_data = await state.get_data()
        current_data['is_editing'] = True
        await state.set_state(PostCreation.waiting_condition)
        await state.set_data(current_data)

        text = """
🏷 <b>Редактирование состояния товара</b>

Выберите новое состояние товара:
"""
        await safe_edit_message(callback, text, PostKeyboards.get_item_condition_menu())
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в edit_condition_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "edit_contact", PostCreation.confirming_post)
async def edit_contact_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование контактов"""
    try:
        current_data = await state.get_data()
        current_data['is_editing'] = True
        await state.set_state(PostCreation.waiting_contact)
        await state.set_data(current_data)

        current_contact = current_data.get('contact_info', '')
        text = f"""
📞 <b>Редактирование контактной информации</b>

Текущие контакты:
{current_contact}

Введите новые контактные данные:
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в edit_contact_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "edit_photos", PostCreation.confirming_post)
async def edit_photos_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование фотографий"""
    try:
        current_data = await state.get_data()
        current_data['photos'] = []  # Очищаем только фото
        current_data['is_editing'] = True
        await state.set_state(PostCreation.waiting_photos)
        await state.set_data(current_data)

        text = """
📸 <b>Редактирование фотографий</b>

Загрузите новые фото.
(Старые будут заменены)

Загрузите первую фотографию:
"""
        await safe_edit_message(callback, text)
        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в edit_photos_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "back_to_preview")
async def back_to_preview_handler(callback: CallbackQuery, state: FSMContext):
    """Возврат к предпросмотру"""
    try:
        await state.update_data(is_editing=False)
        data = await state.get_data()
        photos = data.get('photos', [])
        await state.set_state(PostCreation.confirming_post)

        # Формируем текст предпросмотра
        post_preview = MessageFormatter.format_post_info({
            'title': data.get('title', ''),
            'condition': data.get('condition', ''),
            'description': data.get('description', ''),
            'price': data.get('price', 0),
            'contact_info': data.get('contact_info', ''),
            'post_type': data.get('post_type', ''),
            'photos': photos,
            'created_at': datetime.now()
        })

        text = f"""
✅ <b>Изменения сохранены!</b>

<b>Обновленный пост:</b>

{post_preview}

Все верно? Опубликовать пост?
"""

        if photos and len(photos) > 0:
            try:
                await callback.message.delete()
            except:
                pass

            # Формируем медиагруппу с превью
            media = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=file_id))

            await callback.message.answer_media_group(media=media)
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=PostKeyboards.get_post_confirmation_menu()
            )
        else:
            # Без фотографий - текстовое превью
            await safe_edit_message(callback, text, PostKeyboards.get_post_confirmation_menu())

        await safe_callback_answer(callback)

    except Exception as e:
        logger.error(f"Ошибка в back_to_preview_handler: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при формировании предпросмотра", show_alert=True)


async def back_to_preview_from_message(message: Message, state: FSMContext):
    """Возврат к предпросмотру после редактирования поля через сообщение"""
    try:
        await state.update_data(is_editing=False)
        await state.set_state(PostCreation.confirming_post)

        data = await state.get_data()
        photos = data.get('photos', [])

        # Форматируем превью
        post_preview = MessageFormatter.format_post_info({
            'title': data.get('title', ''),
            'condition': data.get('condition', ''),
            'description': data.get('description', ''),
            'price': data.get('price', 0),
            'contact_info': data.get('contact_info', ''),
            'post_type': data.get('post_type', ''),
            'created_at': datetime.now(),
            'photos': photos
        })

        text = f"""
✅ <b>Изменения сохранены!</b>

<b>Обновленный пост:</b>

{post_preview}

Все верно? Опубликовать пост?
"""

        # Если есть фотографии - показываем их
        if photos and len(photos) > 0:
            media = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=file_id))

            await message.answer_media_group(media=media)
            await message.answer(
                "Выберите действие:",
                reply_markup=PostKeyboards.get_post_confirmation_menu()
            )
        else:
            # Без фотографий - только текст
            await message.answer(
                text,
                reply_markup=PostKeyboards.get_post_confirmation_menu(),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка в back_to_preview_from_message: {e}")
        await message.answer("❌ Произошла ошибка при возврате к превью")


@router.message(~F.photo, PostCreation.waiting_photos)
async def wrong_photo_type(message: Message):
    """Обработчик неправильного типа при ожидании фото"""
    await message.answer("📸 Пожалуйста, отправьте фотографии товара.")


@router.message(~F.text, PostCreation.waiting_title)
async def wrong_title_type(message: Message):
    """Обработчик неправильного типа при ожидании названия"""
    await message.answer("📝 Пожалуйста, отправьте название товара текстом.")


@router.message(~F.text, PostCreation.waiting_description)
async def wrong_description_type(message: Message):
    """Обработчик неправильного типа при ожидании описания"""
    await message.answer("📄 Пожалуйста, отправьте описание товара текстом.")


@router.message(~F.text, PostCreation.waiting_price)
async def wrong_price_type(message: Message):
    """Обработчик неправильного типа при ожидании цены"""
    await message.answer("💰 Пожалуйста, отправьте цену товара числом.")


@router.message(~F.text, PostCreation.waiting_contact)
async def wrong_contact_type(message: Message):
    """Обработчик неправильного типа при ожидании контактов"""
    await message.answer("📞 Пожалуйста, отправьте контактную информацию текстом.")