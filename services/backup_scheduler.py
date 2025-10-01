"""
Планировщик автоматических бэкапов для Richmond Market Bot
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Any, Dict

from utils.backup import BackupManager
from utils.helpers import send_notification_to_admin

logger = logging.getLogger(__name__)


class BackupScheduler:
    """Планировщик автоматических бэкапов"""

    def __init__(self, bot):
        self.bot = bot
        self.backup_manager = BackupManager()
        self.is_running = False
        self.last_backup_date = None
        self.last_cleanup_date = None

    async def start_scheduler(self):
        """Запустить планировщик бэкапов"""
        self.is_running = True
        logger.info("Планировщик бэкапов Richmond Market запущен")

        while self.is_running:
            try:
                now = datetime.now()

                # Создаем бэкап каждый день в 3:00
                if (time(3, 0) <= now.time() <= time(3, 30) and
                    (not self.last_backup_date or self.last_backup_date.date() != now.date())):

                    await self.create_daily_backup()
                    self.last_backup_date = now

                # Очищаем старые бэкапы раз в неделю по воскресеньям в 4:00
                if (now.weekday() == 6 and time(4, 0) <= now.time() <= time(4, 30) and
                    (not self.last_cleanup_date or self.last_cleanup_date.date() != now.date())):

                    await self.cleanup_old_backups()
                    self.last_cleanup_date = now

                # Проверяем каждые 15 минут
                await asyncio.sleep(900)

            except Exception as e:
                logger.error(f"Ошибка в планировщике бэкапов: {e}")
                await asyncio.sleep(300)  # При ошибке ждем 5 минут

    async def create_daily_backup(self):
        """Создать ежедневный бэкап"""
        try:
            logger.info("Создание автоматического ежедневного бэкапа")

            result = await self.backup_manager.create_backup()

            if result['success']:
                size_mb = round(result['size'] / 1024 / 1024, 2)

                await send_notification_to_admin(
                    self.bot,
                    f"""✅ <b>Автоматический бэкап создан</b>

📊 <b>Информация:</b>
• Файл: {result['name']}
• Размер: {size_mb} MB
• Время: {result['created'].strftime('%d.%m.%Y %H:%M')}

Ежедневный бэкап Richmond Market создан успешно."""
                )

                logger.info(f"Ежедневный бэкап создан: {result['name']}")

            else:
                await send_notification_to_admin(
                    self.bot,
                    f"""❌ <b>Ошибка создания бэкапа</b>

Не удалось создать автоматический бэкап Richmond Market.

<b>Ошибка:</b> {result.get('message', 'Неизвестная ошибка')}

Требуется проверка системы!"""
                )

                logger.error(f"Ошибка создания ежедневного бэкапа: {result.get('message')}")

        except Exception as e:
            logger.error(f"Исключение при создании ежедневного бэкапа: {e}")

            try:
                await send_notification_to_admin(
                    self.bot,
                    f"""🚨 <b>Критическая ошибка бэкапа</b>

Произошла критическая ошибка при создании автоматического бэкапа:

<b>Ошибка:</b> {str(e)[:200]}

Немедленно проверьте систему бэкапов!"""
                )
            except:
                logger.error("Не удалось отправить уведомление об ошибке бэкапа")

    async def cleanup_old_backups(self):
        """Очистить старые бэкапы"""
        try:
            logger.info("Начинается автоматическая очистка старых бэкапов")

            cleanup_result = await self.backup_manager.clean_old_backups(days=7)

            if cleanup_result['deleted_count'] > 0:
                freed_mb = round(cleanup_result['freed_space'] / 1024 / 1024, 2)

                await send_notification_to_admin(
                    self.bot,
                    f"""🗑 <b>Очистка старых бэкапов</b>

📊 <b>Результат:</b>
• Удалено файлов: {cleanup_result['deleted_count']}
• Освобождено места: {freed_mb} MB
• Период хранения: {cleanup_result['days']} дней

Автоматическая очистка завершена успешно."""
                )

                logger.info(f"Очищены старые бэкапы: {cleanup_result['deleted_count']} файлов")
            else:
                logger.info("Старых бэкапов для удаления не найдено")

        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")

    def stop_scheduler(self):
        """Остановить планировщик"""
        self.is_running = False
        logger.info("Планировщик бэкапов Richmond Market остановлен")

    async def force_backup(self) -> Dict[str, Any]:
        """Принудительное создание бэкапа (для админ-панели)"""
        try:
            return await self.backup_manager.create_backup()
        except Exception as e:
            logger.error(f"Ошибка принудительного бэкапа: {e}")
            return {
                'success': False,
                'message': f"Ошибка: {str(e)}"
            }
