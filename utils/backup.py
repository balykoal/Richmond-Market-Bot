"""
Система бэкапов базы данных для Richmond Market Bot
"""

import asyncio
import logging
import os
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import settings

logger = logging.getLogger(__name__)


class BackupManager:
    """Менеджер бэкапов базы данных"""

    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.temp_dir = Path("temp_backups")
        self.temp_dir.mkdir(exist_ok=True)

    async def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Создать бэкап базы данных

        Args:
            backup_name: Имя бэкапа (опционально)

        Returns:
            Словарь с результатом создания бэкапа
        """
        try:
            if not backup_name:
                backup_name = f"richmond_market_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            temp_file = self.temp_dir / f"{backup_name}.sql"
            backup_file = self.backup_dir / f"{backup_name}.sql.gz"

            logger.info(f"Начинаем создание бэкапа: {backup_name}")

            # Команда pg_dump
            cmd = [
                "pg_dump",
                f"--host={settings.DB_HOST}",
                f"--port={settings.DB_PORT}",
                f"--username={settings.DB_USER}",
                f"--dbname={settings.DB_NAME}",
                "--no-password",
                "--verbose",
                "--clean",
                "--no-acl",
                "--no-owner",
                "--format=custom",
                f"--file={temp_file}"
            ]

            # Устанавливаем переменную окружения для пароля
            env = os.environ.copy()
            env['PGPASSWORD'] = settings.DB_PASSWORD

            # Выполняем команду
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"pg_dump завершен успешно для {backup_name}")

                # Сжимаем бэкап
                await self._compress_backup(temp_file, backup_file)

                # Получаем информацию о файле
                backup_info = await self._get_backup_info(backup_file)
                backup_info['success'] = True
                backup_info['message'] = "Бэкап создан успешно"

                logger.info(f"Бэкап {backup_name} создан успешно")
                return backup_info

            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"Ошибка создания бэкапа {backup_name}: {error_msg}")

                return {
                    'success': False,
                    'message': f"Ошибка pg_dump: {error_msg[:200]}",
                    'name': backup_name,
                    'size': 0,
                    'created': datetime.now()
                }

        except FileNotFoundError:
            logger.error("pg_dump не найден в системе")
            return {
                'success': False,
                'message': "pg_dump не установлен или недоступен в PATH",
                'name': backup_name or 'unknown',
                'size': 0,
                'created': datetime.now()
            }

        except Exception as e:
            logger.error(f"Исключение при создании бэкапа: {e}")
            return {
                'success': False,
                'message': f"Критическая ошибка: {str(e)[:200]}",
                'name': backup_name or 'unknown',
                'size': 0,
                'created': datetime.now()
            }

    async def _compress_backup(self, source_file: Path, target_file: Path):
        """Сжать бэкап файл асинхронно"""
        try:
            def compress_file():
                with open(source_file, 'rb') as f_in:
                    with gzip.open(target_file, 'wb', compresslevel=9) as f_out:
                        shutil.copyfileobj(f_in, f_out)

            # Выполняем сжатие в отдельном потоке
            await asyncio.get_event_loop().run_in_executor(None, compress_file)

            # Удаляем временный несжатый файл
            if source_file.exists():
                source_file.unlink()

            logger.info(f"Бэкап сжат: {target_file}")

        except Exception as e:
            logger.error(f"Ошибка сжатия бэкапа: {e}")
            raise

    async def _get_backup_info(self, backup_file: Path) -> Dict[str, Any]:
        """Получить информацию о бэкапе"""
        try:
            stat = backup_file.stat()
            return {
                'name': backup_file.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_mtime),
                'path': str(backup_file),
                'compressed': backup_file.suffix == '.gz'
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о бэкапе: {e}")
            return {
                'name': backup_file.name,
                'size': 0,
                'created': datetime.now(),
                'path': str(backup_file),
                'compressed': False
            }

    async def clean_old_backups(self, days: int = 7) -> Dict[str, int]:
        """
        Удалить старые бэкапы

        Args:
            days: Количество дней для хранения бэкапов

        Returns:
            Статистика очистки
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            total_size = 0

            for backup_file in self.backup_dir.glob("richmond_market_*.sql.gz"):
                try:
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        deleted_count += 1
                        total_size += file_size
                        logger.info(f"Удален старый бэкап: {backup_file.name}")
                except Exception as e:
                    logger.error(f"Ошибка удаления бэкапа {backup_file}: {e}")

            # Также очищаем временные файлы
            await self._clean_temp_files()

            return {
                'deleted_count': deleted_count,
                'freed_space': total_size,
                'days': days
            }

        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
            return {'deleted_count': 0, 'freed_space': 0, 'days': days}

    async def _clean_temp_files(self):
        """Очистить временные файлы"""
        try:
            for temp_file in self.temp_dir.glob("*"):
                if temp_file.is_file():
                    file_age = datetime.now() - datetime.fromtimestamp(temp_file.stat().st_mtime)
                    if file_age.total_seconds() > 3600:  # Старше часа
                        temp_file.unlink()
                        logger.debug(f"Удален временный файл: {temp_file.name}")
        except Exception as e:
            logger.error(f"Ошибка очистки временных файлов: {e}")

    async def restore_backup(self, backup_file: str) -> Dict[str, Any]:
        """
        Восстановить базу данных из бэкапа

        Args:
            backup_file: Имя файла бэкапа

        Returns:
            Результат восстановления
        """
        try:
            backup_path = self.backup_dir / backup_file

            if not backup_path.exists():
                return {
                    'success': False,
                    'message': f"Файл бэкапа не найден: {backup_file}"
                }

            temp_file = self.temp_dir / f"restore_{int(datetime.now().timestamp())}.sql"

            # Если файл сжат, распаковываем
            if backup_path.suffix == '.gz':
                await self._decompress_backup(backup_path, temp_file)
            else:
                shutil.copy2(backup_path, temp_file)

            # Команда pg_restore для custom формата
            cmd = [
                "pg_restore",
                f"--host={settings.DB_HOST}",
                f"--port={settings.DB_PORT}",
                f"--username={settings.DB_USER}",
                f"--dbname={settings.DB_NAME}",
                "--no-password",
                "--verbose",
                "--clean",
                "--if-exists",
                str(temp_file)
            ]

            env = os.environ.copy()
            env['PGPASSWORD'] = settings.DB_PASSWORD

            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # Удаляем временный файл
            if temp_file.exists():
                temp_file.unlink()

            if process.returncode == 0:
                logger.info(f"База данных восстановлена из: {backup_file}")
                return {
                    'success': True,
                    'message': f"База данных успешно восстановлена из {backup_file}"
                }
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"Ошибка восстановления: {error_msg}")
                return {
                    'success': False,
                    'message': f"Ошибка восстановления: {error_msg[:200]}"
                }

        except Exception as e:
            logger.error(f"Исключение при восстановлении бэкапа: {e}")
            return {
                'success': False,
                'message': f"Критическая ошибка: {str(e)[:200]}"
            }

    async def _decompress_backup(self, source_file: Path, target_file: Path):
        """Распаковать сжатый бэкап"""
        try:
            def decompress_file():
                with gzip.open(source_file, 'rb') as f_in:
                    with open(target_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

            await asyncio.get_event_loop().run_in_executor(None, decompress_file)
            logger.debug(f"Бэкап распакован: {target_file}")

        except Exception as e:
            logger.error(f"Ошибка распаковки бэкапа: {e}")
            raise

    def get_backup_list(self) -> List[Dict[str, Any]]:
        """Получить список доступных бэкапов"""
        try:
            backups = []
            for backup_file in self.backup_dir.glob("richmond_market_*.sql.gz"):
                try:
                    stat = backup_file.stat()
                    backups.append({
                        'name': backup_file.name,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_mtime),
                        'path': str(backup_file),
                        'size_mb': round(stat.st_size / 1024 / 1024, 2)
                    })
                except Exception as e:
                    logger.error(f"Ошибка обработки файла {backup_file}: {e}")

            return sorted(backups, key=lambda x: x['created'], reverse=True)

        except Exception as e:
            logger.error(f"Ошибка получения списка бэкапов: {e}")
            return []

    async def delete_backup(self, backup_name: str) -> Dict[str, Any]:
        """
        Удалить конкретный бэкап

        Args:
            backup_name: Имя файла бэкапа

        Returns:
            Результат удаления
        """
        try:
            backup_path = self.backup_dir / backup_name

            if not backup_path.exists():
                return {
                    'success': False,
                    'message': f"Файл бэкапа не найден: {backup_name}"
                }

            file_size = backup_path.stat().st_size
            backup_path.unlink()

            logger.info(f"Бэкап удален: {backup_name}")

            return {
                'success': True,
                'message': f"Бэкап {backup_name} успешно удален",
                'freed_space': file_size
            }

        except Exception as e:
            logger.error(f"Ошибка удаления бэкапа {backup_name}: {e}")
            return {
                'success': False,
                'message': f"Ошибка удаления: {str(e)}"
            }

    async def get_backup_stats(self) -> Dict[str, Any]:
        """Получить статистику бэкапов"""
        try:
            backups = self.get_backup_list()

            if not backups:
                return {
                    'total_backups': 0,
                    'total_size': 0,
                    'total_size_mb': 0,
                    'oldest_backup': None,
                    'newest_backup': None,
                    'average_size_mb': 0
                }

            total_size = sum(b['size'] for b in backups)
            oldest_backup = min(backups, key=lambda x: x['created'])
            newest_backup = max(backups, key=lambda x: x['created'])

            return {
                'total_backups': len(backups),
                'total_size': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'oldest_backup': oldest_backup,
                'newest_backup': newest_backup,
                'average_size_mb': round(total_size / len(backups) / 1024 / 1024, 2)
            }

        except Exception as e:
            logger.error(f"Ошибка получения статистики бэкапов: {e}")
            return {
                'total_backups': 0,
                'total_size': 0,
                'error': str(e)
            }