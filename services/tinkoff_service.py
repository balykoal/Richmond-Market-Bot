
"""
Интеграция с Тинькофф Эквайринг API
"""

import aiohttp
import logging
import hashlib
from typing import Dict, Any
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


class TinkoffPaymentService:
    """Сервис для работы с Тинькофф эквайрингом"""

    def __init__(self):
        self.terminal_key = settings.TINKOFF_TERMINAL_KEY
        self.password = settings.TINKOFF_PASSWORD
        self.api_url = settings.TINKOFF_API_URL

    async def create_payment(self, amount: float, description: str, user_id: int, post_type: str) -> Dict[str, Any]:
        """
        Создание платежа в Тинькофф

        Args:
            amount: Сумма в рублях
            description: Описание платежа
            user_id: ID пользователя Telegram
            post_type: Тип поста (regular/pinned)

        Returns:
            Словарь с данными платежа
        """
        try:
            order_id = f"RC_{user_id}_{int(datetime.now().timestamp())}"
            amount_kopecks = int(amount * 100)  # В копейках

            payment_data = {
                "TerminalKey": self.terminal_key,
                "Amount": amount_kopecks,
                "OrderId": order_id,
                "Description": description,
                "PayType": "O",
                "Language": "ru",
                "NotificationURL": f"https://your-domain.com/webhook/tinkoff",  # TODO: заменить на реальный URL
                "SuccessURL": f"https://t.me/{settings.BOT_TOKEN.split(':')[0]}",
                "FailURL": f"https://t.me/{settings.BOT_TOKEN.split(':')[0]}",
                "DATA": {
                    "user_id": str(user_id),
                    "post_type": post_type,
                    "bot_name": "RC_Exchange"
                }
            }

            # Генерируем токен (подпись)
            payment_data["Token"] = self._generate_token(payment_data)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_url}/Init",
                        json=payment_data
                ) as response:
                    result = await response.json()

                    if result.get("Success"):
                        return {
                            "success": True,
                            "payment_id": result["PaymentId"],
                            "confirmation_url": result["PaymentURL"],
                            "order_id": order_id,
                            "status": "pending",
                            "amount": amount
                        }
                    else:
                        logger.error(f"Ошибка создания платежа Тинькофф: {result}")
                        return {
                            "success": False,
                            "error": result.get("Message", "Неизвестная ошибка"),
                            "error_code": result.get("ErrorCode")
                        }

        except Exception as e:
            logger.error(f"Исключение при создании платежа Тинькофф: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def check_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """
        Проверка статуса платежа

        Args:
            payment_id: ID платежа в системе Тинькофф

        Returns:
            Статус платежа
        """
        try:
            request_data = {
                "TerminalKey": self.terminal_key,
                "PaymentId": payment_id
            }

            request_data["Token"] = self._generate_token(request_data)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_url}/GetState",
                        json=request_data
                ) as response:
                    result = await response.json()

                    if result.get("Success"):
                        status_map = {
                            "NEW": "pending",
                            "FORM_SHOWED": "pending",
                            "AUTHORIZING": "pending",
                            "3DS_CHECKING": "pending",
                            "3DS_CHECKED": "pending",
                            "AUTHORIZED": "pending",
                            "CONFIRMING": "pending",
                            "CONFIRMED": "succeeded",
                            "CANCELED": "canceled",
                            "REJECTED": "canceled"
                        }

                        tinkoff_status = result.get("Status", "NEW")
                        mapped_status = status_map.get(tinkoff_status, "pending")

                        return {
                            "success": True,
                            "status": mapped_status,
                            "paid": mapped_status == "succeeded",
                            "amount": result.get("Amount", 0) / 100,
                            "order_id": result.get("OrderId"),
                            "tinkoff_status": tinkoff_status
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("Message", "Ошибка проверки статуса")
                        }

        except Exception as e:
            logger.error(f"Ошибка проверки статуса платежа: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_payment(self, payment_id: str) -> Dict[str, Any]:
        """Отмена платежа"""
        try:
            request_data = {
                "TerminalKey": self.terminal_key,
                "PaymentId": payment_id
            }

            request_data["Token"] = self._generate_token(request_data)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_url}/Cancel",
                        json=request_data
                ) as response:
                    result = await response.json()
                    return {
                        "success": result.get("Success", False),
                        "message": result.get("Message", "")
                    }

        except Exception as e:
            logger.error(f"Ошибка отмены платежа: {e}")
            return {"success": False, "error": str(e)}

    def _generate_token(self, data: dict) -> str:
        """
        Генерация токена для подписи запроса

        Args:
            data: Данные запроса

        Returns:
            SHA256 хеш для подписи
        """
        # Исключаем служебные поля из подписи
        excluded_fields = {"Token", "DATA", "Receipt", "Shops"}

        # Собираем значения для подписи
        values = []
        for key in sorted(data.keys()):
            if key not in excluded_fields:
                value = data[key]
                if isinstance(value, bool):
                    value = "true" if value else "false"
                values.append(str(value))

        # Добавляем пароль в конец
        values.append(self.password)

        # Создаем строку для хеширования
        token_string = "".join(values)

        # Возвращаем SHA256 хеш
        return hashlib.sha256(token_string.encode('utf-8')).hexdigest()

    def process_webhook(self, webhook_data: dict) -> Dict[str, Any]:
        """
        Обработка webhook от Тинькофф

        Args:
            webhook_data: Данные webhook

        Returns:
            Обработанные данные
        """
        try:
            # Проверяем подпись
            received_token = webhook_data.pop("Token", "")
            calculated_token = self._generate_token(webhook_data)

            if received_token != calculated_token:
                logger.warning("Неверная подпись webhook от Тинькофф")
                return {"success": False, "error": "Invalid signature"}

            status = webhook_data.get("Status")
            payment_id = webhook_data.get("PaymentId")
            amount = webhook_data.get("Amount", 0) / 100
            order_id = webhook_data.get("OrderId")

            # Извлекаем данные пользователя из OrderId
            try:
                parts = order_id.split("_")
                user_id = int(parts[1]) if len(parts) >= 2 else None
            except:
                user_id = None

            if status == "CONFIRMED":
                return {
                    "success": True,
                    "event": "payment_success",
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount": amount,
                    "user_id": user_id
                }
            elif status in ["CANCELED", "REJECTED"]:
                return {
                    "success": True,
                    "event": "payment_failed",
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "user_id": user_id,
                    "reason": "Payment canceled or rejected"
                }
            else:
                return {
                    "success": True,
                    "event": "payment_status_update",
                    "payment_id": payment_id,
                    "status": status,
                    "user_id": user_id
                }

        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {e}")
            return {"success": False, "error": str(e)}