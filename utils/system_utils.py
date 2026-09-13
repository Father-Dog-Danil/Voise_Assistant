"""
Системные утилиты
Содержит функции для работы с Windows API, процессами и окнами
"""

import os
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import psutil
import win32gui
import win32con
import win32process

from config import PROTECTED_PROCESSES, PROTECTED_TITLES

logger = logging.getLogger(__name__)


def get_window_info(hwnd: int) -> Optional[Dict]:
    """
    Получает информацию об окне по его дескриптору

    Args:
        hwnd (int): Дескриптор окна

    Returns:
        Optional[Dict]: Информация об окне или None
    """
    try:
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) != "":
            window_text = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)

            # Фильтруем системные окна
            if (window_text and
                    class_name not in ['Progman', 'WorkerW', 'Shell_TrayWnd', 'Button', 'Static'] and
                    'MSCTFIME UI' not in class_name):

                _, pid = win32process.GetWindowThreadProcessId(hwnd)

                try:
                    process = psutil.Process(pid)
                    exe_path = process.exe()
                    process_name = process.name()
                except:
                    exe_path = ""
                    process_name = ""

                return {
                    'hwnd': hwnd,
                    'title': window_text,
                    'class_name': class_name,
                    'pid': pid,
                    'exe_path': exe_path,
                    'process_name': process_name,
                    'timestamp': datetime.now().isoformat()
                }
    except Exception as e:
        logger.error(f"ошибка получения информации об окне: {e}")

    return None


def is_protected_window(window_info: Optional[Dict]) -> bool:
    """
    Проверяет является ли окно защищенным (нельзя закрывать)

    Args:
        window_info (Optional[Dict]): Информация об окне

    Returns:
        bool: True если окно защищено
    """
    if not window_info:
        return False

    # Проверяем по имени процесса
    process_name = window_info.get('process_name', '').lower()
    if any(protected in process_name for protected in PROTECTED_PROCESSES):
        return True

    # Проверяем по заголовку окна
    title_lower = window_info.get('title', '').lower()
    if any(protected_title in title_lower for protected_title in PROTECTED_TITLES):
        return True

    return False


def get_all_visible_windows() -> List[Dict]:
    """
    Получает список всех видимых окон

    Returns:
        List[Dict]: Список информации об окнах
    """
    windows = []

    def callback(hwnd, extra):
        window_info = get_window_info(hwnd)
        if window_info and not is_protected_window(window_info):
            windows.append(window_info)

    win32gui.EnumWindows(callback, None)
    return windows


def close_window_safe(window_info: Dict) -> bool:
    """
    Безопасно закрывает окно

    Args:
        window_info (Dict): Информация об окне

    Returns:
        bool: True если окно закрыто
    """
    try:
        if is_protected_window(window_info):
            logger.warning(f"окно защищено, пропускаю: {window_info.get('title', '')}")
            return False

        hwnd = window_info.get('hwnd')
        if hwnd and win32gui.IsWindow(hwnd):
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            logger.info(f"закрыто окно: {window_info.get('title', '')}")
            return True
    except Exception as e:
        logger.error(f"ошибка закрытия окна {window_info.get('title', '')}: {e}")

    return False


def minimize_window_safe(window_info: Dict) -> bool:
    """
    Безопасно сворачивает окно

    Args:
        window_info (Dict): Информация об окне

    Returns:
        bool: True если окно свернуто
    """
    try:
        if is_protected_window(window_info):
            logger.warning(f"окно защищено, пропускаю: {window_info.get('title', '')}")
            return False

        hwnd = window_info.get('hwnd')
        if hwnd and win32gui.IsWindow(hwnd):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) != "":
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                logger.info(f"свернуто окно: {window_info.get('title', '')}")
                return True
    except Exception as e:
        logger.error(f"ошибка сворачивания окна {window_info.get('title', '')}: {e}")

    return False


def restore_window(window_info: Dict) -> bool:
    """
    Восстанавливает окно из свернутого состояния

    Args:
        window_info (Dict): Информация об окне

    Returns:
        bool: True если окно восстановлено
    """
    try:
        hwnd = window_info.get('hwnd')
        if hwnd and win32gui.IsWindow(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            logger.info(f"восстановлено окно: {window_info.get('title', '')}")
            return True
    except Exception as e:
        logger.error(f"ошибка восстановления окна {window_info.get('title', '')}: {e}")

    return False


def find_processes_by_names(process_names: List[str]) -> List[Dict]:
    """
    Находит процессы по именам

    Args:
        process_names (List[str]): Список имен процессов

    Returns:
        List[Dict]: Список найденных процессов
    """
    found_processes = []

    for proc in psutil.process_iter(['name', 'pid', 'exe']):
        try:
            proc_name = proc.info['name'].lower()
            if any(pname.lower() in proc_name for pname in process_names):
                found_processes.append({
                    'name': proc.info['name'],
                    'pid': proc.info['pid'],
                    'exe': proc.info['exe'] if proc.info['exe'] else ""
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return found_processes


def terminate_processes(process_names: List[str]) -> Tuple[int, List[Dict]]:
    """
    Завершает процессы по именам

    Args:
        process_names (List[str]): Список имен процессов

    Returns:
        Tuple[int, List[Dict]]: (количество завершенных, список завершенных процессов)
    """
    # Сохраняем информацию о процессах перед завершением
    processes_before = find_processes_by_names(process_names)

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

    return closed_count, processes_before


def get_process_info(pid: int) -> Optional[Dict]:
    """
    Получает информацию о процессе по PID

    Args:
        pid (int): PID процесса

    Returns:
        Optional[Dict]: Информация о процессе
    """
    try:
        process = psutil.Process(pid)
        return {
            'pid': pid,
            'name': process.name(),
            'exe': process.exe(),
            'status': process.status(),
            'create_time': process.create_time(),
            'cpu_percent': process.cpu_percent(),
            'memory_percent': process.memory_percent()
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def is_process_running(process_name: str) -> bool:
    """
    Проверяет запущен ли процесс

    Args:
        process_name (str): Имя процесса

    Returns:
        bool: True если процесс запущен
    """
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def get_system_info() -> Dict:
    """
    Получает информацию о системе

    Returns:
        Dict: Информация о системе
    """
    return {
        'cpu_count': psutil.cpu_count(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_total': psutil.virtual_memory().total,
        'memory_available': psutil.virtual_memory().available,
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
    }


def execute_command_with_timeout(command: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
    """
    Выполняет системную команду с таймаутом

    Args:
        command (List[str]): Команда для выполнения
        timeout (int): Таймаут в секундах

    Returns:
        Tuple[bool, str, str]: (успех, stdout, stderr)
    """
    import subprocess

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"таймаут при выполнении команды: {command}")
        return False, "", "timeout"
    except Exception as e:
        logger.error(f"ошибка выполнения команды {command}: {e}")
        return False, "", str(e)


def run_powershell_command(command: str, timeout: int = 10) -> Tuple[bool, str, str]:
    """
    Выполняет PowerShell команду

    Args:
        command (str): PowerShell команда
        timeout (int): Таймаут в секундах

    Returns:
        Tuple[bool, str, str]: (успех, stdout, stderr)
    """
    import subprocess

    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='cp866'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"таймаут при выполнении PowerShell команды")
        return False, "", "timeout"
    except Exception as e:
        logger.error(f"ошибка выполнения PowerShell команды: {e}")
        return False, "", str(e)


def is_admin() -> bool:
    """
    Проверяет запущен ли скрипт с правами администратора

    Returns:
        bool: True если есть права администратора
    """
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def get_uptime() -> str:
    """
    Возвращает время работы системы

    Returns:
        str: Время работы в формате "X дней Y часов Z минут"
    """
    try:
        import psutil
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60

        return f"{days} дней {hours} часов {minutes} минут"
    except Exception as e:
        logger.error(f"ошибка получения времени работы: {e}")
        return "не удалось определить"


def open_file_or_folder(path: str) -> bool:
    """
    Открывает файл или папку в проводнике

    Args:
        path (str): Путь к файлу или папке

    Returns:
        bool: True если успешно открыто
    """
    try:
        if os.path.exists(path):
            os.startfile(path)
            logger.info(f"открыто: {path}")
            return True
        else:
            logger.error(f"путь не существует: {path}")
            return False
    except Exception as e:
        logger.error(f"ошибка открытия {path}: {e}")
        return False


def lock_workstation() -> bool:
    """
    Блокирует рабочую станцию

    Returns:
        bool: True если успешно заблокирована
    """
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        logger.info("рабочая станция заблокирована")
        return True
    except Exception as e:
        logger.error(f"ошибка блокировки рабочей станции: {e}")
        return False


def get_active_window_title() -> Optional[str]:
    """
    Получает заголовок активного окна

    Returns:
        Optional[str]: Заголовок активного окна
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd)
    except Exception as e:
        logger.error(f"ошибка получения заголовка активного окна: {e}")
        return None


def set_window_foreground(hwnd: int) -> bool:
    """
    Переводит окно на передний план

    Args:
        hwnd (int): Дескриптор окна

    Returns:
        bool: True если успешно
    """
    try:
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        logger.error(f"ошибка перевода окна на передний план: {e}")
        return False