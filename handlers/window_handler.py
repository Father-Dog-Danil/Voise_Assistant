"""
Обработчик управления окнами
Содержит логику для работы с окнами Windows
"""

import logging
import time
from typing import Optional, Tuple, List, Dict

import pyautogui
import win32gui
import win32con

from handlers.base_handler import BaseHandler, execute_delayed_task
from utils.system_utils import (
    get_window_info,
    is_protected_window,
    close_window_safe,
    minimize_window_safe,
    restore_window
)

logger = logging.getLogger(__name__)


class WindowHandler(BaseHandler):
    """
    Обработчик для управления окнами
    """

    def __init__(self):
        """Инициализация обработчика окон"""
        super().__init__()
        self.keywords = [
            'окна', 'окно', 'сверни', 'разверни', 'закрой все',
            'рабочий стол', 'десктоп', 'восстанови окна'
        ]
        self.response_type = 'close_windows'

    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает команду управления окнами

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Закрыть все окна
        if any(word in command for word in ['закрой окна', 'закрой все', 'закрыть всё', 'закрыть окна', 'убери окна']):
            logger.info("закрываю все окна")
            self.response_type = 'close_windows'
            return None, lambda: execute_delayed_task(self.close_all_windows_safe), self.response_type

        # Свернуть все окна
        if any(word in command for word in
               ['сверни окна', 'сверни все', 'свернуть всё', 'свернуть окна', 'минимизируй']):
            logger.info("сворачиваю все окна")
            self.response_type = 'minimize'
            return None, lambda: execute_delayed_task(self.minimize_all_windows_safe), self.response_type

        # Восстановить окна
        if any(word in command for word in
               ['верни окна', 'восстанови окна', 'покажи окна', 'раскрой всё', 'верни всё']):
            logger.info("восстанавливаю окна")
            self.response_type = 'restore'
            return None, lambda: execute_delayed_task(self.restore_all_windows), self.response_type

        # Показать рабочий стол
        if any(word in command for word in ['рабочий стол', 'покажи рабочий стол', 'десктоп', 'показать рабочий стол']):
            logger.info("показываю рабочий стол")
            self.response_type = 'minimize'
            return None, lambda: execute_delayed_task(self.show_desktop), self.response_type

        return None, None, ""

    def close_all_windows_safe(self) -> bool:
        """
        Безопасно закрывает все окна (не трогает защищенные)

        Returns:
            bool: True если успешно
        """
        try:
            closed_windows = []

            def callback(hwnd, extra):
                window_info = get_window_info(hwnd)
                if window_info and not is_protected_window(window_info):
                    if close_window_safe(window_info):
                        closed_windows.append(window_info)
                        time.sleep(0.1)

            win32gui.EnumWindows(callback, None)
            time.sleep(1)

            logger.info(f"✅ закрыто {len(closed_windows)} окон")

            if closed_windows:
                self.add_to_history(
                    "закрытие окон",
                    {"closed_windows": closed_windows},
                    lambda: self.restore_closed_windows(closed_windows)
                )

            return True

        except Exception as e:
            logger.error(f"❌ ошибка закрытия окон: {e}")
            return False

    def restore_closed_windows(self, closed_windows_list: List[Dict]) -> bool:
        """
        Восстанавливает закрытые окна

        Args:
            closed_windows_list (List[Dict]): Список закрытых окон

        Returns:
            bool: True если успешно восстановлено
        """
        import os
        import subprocess

        restored_count = 0
        for window_info in closed_windows_list:
            try:
                if window_info.get('exe_path') and os.path.exists(window_info['exe_path']):
                    subprocess.Popen(window_info['exe_path'])
                    restored_count += 1
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"ошибка восстановления окна: {e}")

        logger.info(f"восстановлено {restored_count} окон")
        return restored_count > 0

    def minimize_all_windows_safe(self) -> bool:
        """
        Безопасно сворачивает все окна

        Returns:
            bool: True если успешно
        """
        try:
            minimized_windows = []

            def callback(hwnd, extra):
                window_info = get_window_info(hwnd)
                if window_info and not is_protected_window(window_info):
                    if minimize_window_safe(window_info):
                        minimized_windows.append(window_info)

            win32gui.EnumWindows(callback, None)
            logger.info(f"✅ свернуто {len(minimized_windows)} окон")

            if minimized_windows:
                self.add_to_history(
                    "сворачивание окон",
                    {"minimized_windows": minimized_windows},
                    lambda: self.restore_minimized_windows(minimized_windows)
                )

            return True

        except Exception as e:
            logger.error(f"❌ ошибка сворачивания окон: {e}")
            return False

    def restore_minimized_windows(self, minimized_windows_list: List[Dict]) -> bool:
        """
        Восстанавливает свернутые окна

        Args:
            minimized_windows_list (List[Dict]): Список свернутых окон

        Returns:
            bool: True если успешно восстановлено
        """
        restored_count = 0
        for window_info in minimized_windows_list:
            try:
                if restore_window(window_info):
                    restored_count += 1
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"ошибка восстановления окна: {e}")

        logger.info(f"восстановлено {restored_count} свернутых окон")
        return restored_count > 0

    def restore_all_windows(self) -> bool:
        """
        Восстанавливает все окна через горячие клавиши

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('win', 'shift', 'm')
            time.sleep(0.5)
            logger.info("✅ все окна восстановлены")
            return True
        except Exception as e:
            logger.error(f"❌ ошибка восстановления окон: {e}")
            return False

    def show_desktop(self) -> bool:
        """
        Показывает рабочий стол

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('win', 'd')
            logger.info("✅ рабочий стол показан")
            return True
        except Exception as e:
            logger.error(f"❌ ошибка показа рабочего стола: {e}")
            return False


# Создаем глобальный экземпляр обработчика
window_handler = WindowHandler()


# Функции для обратной совместимости
def close_all_windows_safe() -> bool:
    """Обертка для закрытия всех окон"""
    return window_handler.close_all_windows_safe()


def minimize_all_windows_safe() -> bool:
    """Обертка для сворачивания всех окон"""
    return window_handler.minimize_all_windows_safe()


def restore_all_windows() -> bool:
    """Обертка для восстановления окон"""
    return window_handler.restore_all_windows()


def show_desktop() -> bool:
    """Обертка для показа рабочего стола"""
    return window_handler.show_desktop()


def restore_closed_windows(closed_windows_list: List[Dict]) -> bool:
    """Обертка для восстановления закрытых окон"""
    return window_handler.restore_closed_windows(closed_windows_list)


def restore_minimized_windows(minimized_windows_list: List[Dict]) -> bool:
    """Обертка для восстановления свернутых окон"""
    return window_handler.restore_minimized_windows(minimized_windows_list)