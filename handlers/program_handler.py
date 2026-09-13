"""
Обработчик запуска и закрытия программ
Содержит логику для работы с приложениями
"""

import os
import time
import logging
import subprocess
from typing import Optional, Dict, List, Tuple

import psutil

from handlers.base_handler import BaseHandler, execute_delayed_task
from services.program_database import program_database
from utils.text_processing import extract_app_name

logger = logging.getLogger(__name__)


class ProgramHandler(BaseHandler):
    """
    Обработчик для запуска и закрытия программ
    """

    def __init__(self):
        """Инициализация обработчика программ"""
        super().__init__()
        self.keywords = [
            'запусти', 'открой', 'включи', 'запустить', 'открыть', 'включить',
            'закрой', 'выключи', 'заверши', 'закрыть', 'выключить',
            'телеграм', 'дискорд', 'хром', 'яндекс', 'стим', 'вскод',
            'пайчарм', 'спотифай', 'ворд', 'word', 'excel', 'powerpoint'
        ]
        self.response_type = 'launch'
        self.launched_processes = []

    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает команду запуска/закрытия программ

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Определяем тип команды
        is_close_command = any(
            word in command for word in ['закрой', 'выключи', 'заверши', 'закрыть', 'выключить']
        )
        is_launch_command = any(
            word in command for word in ['запусти', 'открой', 'включи', 'открыть', 'включить', 'запустить']
        )

        # Ищем программу в базе данных
        program_info = program_database.find_program_by_name(command, is_close_command=is_close_command)

        if program_info:
            display_name = program_info.get("display_name", "программу")

            if is_close_command:
                logger.info(f"🔴 закрываю программу из базы: {display_name}")
                self.response_type = 'close'
                return None, lambda: execute_delayed_task(self.close_program, program_info), self.response_type

            elif is_launch_command:
                logger.info(f"🔄 найдена программа в базе: {display_name}")
                self.response_type = 'launch'
                return None, lambda: execute_delayed_task(self.launch_program, program_info), self.response_type

        # Если не нашли в базе, пробуем старый поиск для запуска
        if is_launch_command:
            app_name = extract_app_name(command)
            if app_name:
                logger.info(f"ищу приложение через старый поиск: {app_name}")
                self.response_type = 'launch'
                return None, lambda: execute_delayed_task(self.search_and_launch_app, app_name), self.response_type

        return None, None, ""

    def launch_program(self, program_info: Dict) -> bool:
        """
        Запускает программу по информации из базы данных

        Args:
            program_info (Dict): Информация о программе

        Returns:
            bool: True если успешно запущено
        """
        try:
            exe_path = program_info.get("exe_path", "")
            display_name = program_info.get("display_name", "программу")

            if not exe_path:
                logger.error(f"путь к программе не указан для: {display_name}")
                return False

            if not os.path.exists(exe_path):
                logger.error(f"путь к программе не найден: {exe_path}")
                return False

            logger.info(f"🚀 запускаю {display_name}: {exe_path}")

            # Запускаем с дополнительными аргументами если есть
            launch_args = program_info.get("launch_args", [])
            if launch_args:
                process = subprocess.Popen([exe_path] + launch_args)
            else:
                process = subprocess.Popen([exe_path])

            self.launched_processes.append(process)

            # Добавляем в историю для возможности отмены
            self.add_to_history(
                f"запуск {display_name}",
                {"program_info": program_info, "action_type": "launch"},
                lambda: self.close_program(program_info)
            )

            logger.info(f"✅ {display_name} успешно запущена")
            return True

        except Exception as e:
            logger.error(f"❌ ошибка запуска программы: {e}")
            return False

    def close_program(self, program_info: Dict) -> bool:
        """
        Закрывает программу по информации из базы данных

        Args:
            program_info (Dict): Информация о программе

        Returns:
            bool: True если успешно закрыто
        """
        try:
            display_name = program_info.get("display_name", "программу")
            process_names = program_info.get("process_names", [])

            # Если process_names не указан, пытаемся извлечь из exe_path
            if not process_names and "exe_path" in program_info:
                exe_name = os.path.basename(program_info["exe_path"])
                process_names = [exe_name]

            # Если все еще нет process_names, логируем ошибку
            if not process_names:
                logger.error(f"❌ не указаны process_names для программы: {display_name}")
                return False

            logger.info(f"🔴 закрываю {display_name} (процессы: {process_names})")

            # Сохраняем информацию о запущенных процессах перед закрытием
            processes_before = self._find_processes(process_names)

            closed_count = 0
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info['name'].lower()
                    if any(pname.lower() in proc_name for pname in process_names):
                        proc.terminate()
                        closed_count += 1
                        logger.info(f"закрыт процесс: {proc.info['name']} (PID: {proc.info['pid']})")
                        time.sleep(0.1)
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"не удалось закрыть процесс {proc.info['name']}: {e}")
                    continue

            if closed_count > 0:
                logger.info(f"✅ успешно закрыто {closed_count} процессов для {display_name}")

                # Добавляем в историю для возможности отмены (восстановления)
                self.add_to_history(
                    f"закрытие {display_name}",
                    {
                        "program_info": program_info,
                        "action_type": "close",
                        "processes_before": processes_before,
                        "closed_count": closed_count
                    },
                    lambda: self.restore_program(program_info, processes_before)
                )

                return True
            else:
                logger.warning(f"⚠️ не найдено запущенных процессов для {display_name}")
                # Пытаемся закрыть через taskkill
                try:
                    for pname in process_names:
                        subprocess.run(["taskkill", "/f", "/im", pname], timeout=5, capture_output=True)
                        logger.info(f"попытка закрыть через taskkill: {pname}")

                    # Добавляем в историю даже если закрыли через taskkill
                    self.add_to_history(
                        f"закрытие {display_name}",
                        {
                            "program_info": program_info,
                            "action_type": "close",
                            "processes_before": processes_before,
                            "closed_count": closed_count
                        },
                        lambda: self.restore_program(program_info, processes_before)
                    )

                    return True
                except Exception as e:
                    logger.error(f"❌ ошибка закрытия через taskkill: {e}")
                    return False

        except Exception as e:
            logger.error(f"❌ ошибка закрытия программы: {e}")
            return False

    def restore_program(self, program_info: Dict, processes_before: List[Dict]) -> bool:
        """
        Восстанавливает закрытую программу

        Args:
            program_info (Dict): Информация о программе
            processes_before (List[Dict]): Информация о процессах до закрытия

        Returns:
            bool: True если успешно восстановлено
        """
        try:
            display_name = program_info.get("display_name", "программу")

            logger.info(f"🔄 восстанавливаю {display_name}")

            # Пытаемся запустить программу
            success = self.launch_program(program_info)

            if success:
                logger.info(f"✅ {display_name} успешно восстановлена")
            else:
                logger.error(f"❌ не удалось восстановить {display_name}")

            return success

        except Exception as e:
            logger.error(f"❌ ошибка восстановления программы: {e}")
            return False

    def search_and_launch_app(self, app_name: str) -> bool:
        """
        Ищет и запускает приложение через Windows

        Args:
            app_name (str): Название приложения

        Returns:
            bool: True если успешно запущено
        """
        try:
            logger.info(f"ищу приложение: {app_name}")

            # Сначала ищем в базе данных
            program_info = program_database.find_program_by_name(app_name)
            if program_info:
                return self.launch_program(program_info)

            # Если не нашли в базе, используем PowerShell
            ps_command = f'''
                $apps = Get-StartApps
                $foundApp = $apps | Where-Object {{ 
                    $_.Name -like "*{app_name}*"
                }}
                if ($foundApp) {{
                    $app = $foundApp | Select-Object -First 1
                    Start-Process "explorer.exe" "shell:appsFolder\\$($app.AppID)"
                    exit 0
                }} else {{
                    exit 1
                }}
            '''

            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='cp866'
            )

            if result.returncode == 0:
                logger.info(f"запущено: {app_name}")
                return True
            else:
                logger.warning(f"приложение '{app_name}' не найдено")
                return False

        except Exception as e:
            logger.error(f"ошибка поиска приложения: {e}")
            return False

    def _find_processes(self, process_names: List[str]) -> List[Dict]:
        """
        Находит запущенные процессы по именам

        Args:
            process_names (List[str]): Список имен процессов

        Returns:
            List[Dict]: Список найденных процессов
        """
        processes = []
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                if any(pname.lower() in proc_name for pname in process_names):
                    processes.append({
                        'name': proc.info['name'],
                        'pid': proc.info['pid'],
                        'exe': proc.info['exe'] if proc.info['exe'] else ""
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    def launch_work_apps(self) -> bool:
        """
        Запускает рабочие приложения (телеграм, яндекс, хром)

        Returns:
            bool: True если все запущены
        """
        logger.info("запускаю рабочие приложения")

        apps_to_launch = ['телеграм', 'яндекс', 'хром']
        success_count = 0

        for app_name in apps_to_launch:
            try:
                program_info = program_database.find_program_by_name(app_name)
                if program_info:
                    if self.launch_program(program_info):
                        success_count += 1
                time.sleep(1)
            except Exception as e:
                logger.error(f"ошибка запуска {app_name}: {e}")

        logger.info(f"запущено {success_count} из {len(apps_to_launch)} приложений")
        return success_count == len(apps_to_launch)


# Специализированные функции для конкретных программ
def open_telegram() -> bool:
    """Открывает Telegram"""
    program_info = program_database.find_program_by_name("телеграм")
    if program_info:
        handler = ProgramHandler()
        return handler.launch_program(program_info)
    return False


def open_chrome() -> bool:
    """Открывает Chrome"""
    program_info = program_database.find_program_by_name("хром")
    if program_info:
        handler = ProgramHandler()
        return handler.launch_program(program_info)
    return False


def open_spotify() -> bool:
    """Открывает Spotify"""
    program_info = program_database.find_program_by_name("спотифай")
    if program_info:
        handler = ProgramHandler()
        return handler.launch_program(program_info)
    return False


def open_yandex_browser() -> bool:
    """Открывает Яндекс Браузер"""
    program_info = program_database.find_program_by_name("яндекс")
    if program_info:
        handler = ProgramHandler()
        return handler.launch_program(program_info)
    return False


def open_yandex_incognito(search_query: str = "") -> bool:
    """
    Запускает Яндекс в режиме инкогнито

    Args:
        search_query (str): Поисковый запрос (опционально)

    Returns:
        bool: True если успешно запущено
    """
    try:
        program_info = program_database.find_program_by_name("яндекс")
        if program_info:
            exe_path = program_info.get("exe_path", "")

            if search_query:
                import urllib.parse
                encoded_query = urllib.parse.quote(search_query)
                url = f"https://yandex.ru/search/?text={encoded_query}"
                subprocess.Popen([exe_path, "--incognito", url])
            else:
                subprocess.Popen([exe_path, "--incognito"])

            logger.info("яндекс браузер запущен в режиме инкогнито")
            return True
        else:
            logger.error("яндекс браузер не найден в базе данных")
            return False
    except Exception as e:
        logger.error(f"ошибка запуска яндекс браузера в инкогнито: {e}")
        return False


# Создаем глобальный экземпляр обработчика
program_handler = ProgramHandler()