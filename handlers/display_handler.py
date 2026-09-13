"""
Обработчик управления дисплеями
Содержит логику для работы с яркостью и мониторами
"""

import logging
import subprocess
from typing import Optional, Tuple, Dict

import screen_brightness_control as sbc

from handlers.base_handler import BaseHandler, execute_delayed_task
from utils.text_processing import extract_brightness_level
from config import SPECIAL_MONITORS

logger = logging.getLogger(__name__)


class DisplayHandler(BaseHandler):
    """
    Обработчик для управления яркостью и мониторами
    """

    def __init__(self):
        """Инициализация обработчика дисплеев"""
        super().__init__()
        self.keywords = [
            'яркость', 'монитор', 'экран', 'дисплей',
            'дублировать', 'расширить', 'клонировать'
        ]
        self.response_type = 'brightness'
        self.current_monitor_mode = "extend"
        self.monitor_brightness_history = {}

    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает команду управления дисплеями

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Обработка яркости
        if any(word in command for word in ['яркость', 'ярко', 'свет']):
            brightness_level = extract_brightness_level(command, self.get_current_brightness_for_monitors())
            if brightness_level is not None:
                logger.info(f"устанавливаю яркость: {brightness_level}%")
                self.response_type = 'brightness'
                return None, lambda: execute_delayed_task(self.set_brightness_by_level,
                                                          brightness_level), self.response_type

        # Один монитор
        if any(word in command for word in ['1 монитор', 'один монитор', 'только 1 экран', 'выключи второй монитор']):
            logger.info("переключаю на один монитор")
            self.response_type = 'monitor'
            return None, lambda: execute_delayed_task(self.set_single_monitor), self.response_type

        # Два монитора (расширение)
        if any(word in command for word in
               ['2 монитора', 'два монитора', 'оба монитора', 'расширение экрана', 'расширить экран']):
            logger.info("переключаю на режим расширения")
            self.response_type = 'monitor'
            return None, lambda: execute_delayed_task(self.set_extend_monitors), self.response_type

        # Дублирование
        if any(word in command for word in
               ['дублировать', 'клонировать экран', 'одинаковые экраны', 'зеркало', 'копия экрана']):
            logger.info("переключаю на режим дублирования")
            self.response_type = 'monitor'
            return None, lambda: execute_delayed_task(self.set_duplicate_monitors), self.response_type

        return None, None, ""

    def get_current_brightness_for_monitors(self) -> Dict:
        """
        Получает текущую яркость для всех мониторов

        Returns:
            Dict: Словарь с яркостью для каждого монитора
        """
        try:
            monitors = sbc.list_monitors()
            current_brightness = {}

            for monitor in monitors:
                try:
                    brightness = sbc.get_brightness(display=monitor)
                    if isinstance(brightness, list):
                        brightness = brightness[0] if brightness else 0
                    current_brightness[monitor] = brightness
                except Exception as e:
                    logger.error(f"ошибка получения яркости для {monitor}: {e}")
                    current_brightness[monitor] = 50

            return current_brightness
        except Exception as e:
            logger.error(f"ошибка получения текущей яркости: {e}")
            return {}

    def set_brightness_scaled(self, level: int) -> str:
        """
        Устанавливает яркость с учетом разных максимумов мониторов

        Args:
            level (int): Уровень яркости (0-100)

        Returns:
            str: Результат операции
        """
        try:
            # Сохраняем текущую яркость перед изменением
            old_brightness = self.get_current_brightness_for_monitors()

            monitors = sbc.list_monitors()
            success_count = 0

            for monitor in monitors:
                try:
                    # Проверяем специальные мониторы
                    max_brightness = 100
                    for special_name, special_config in SPECIAL_MONITORS.items():
                        if special_name in monitor:
                            max_brightness = special_config.get('max_brightness', 100)
                            break

                    scaled_level = int((level / 100) * max_brightness)
                    sbc.set_brightness(scaled_level, display=monitor)
                    logger.info(f"{monitor}: {scaled_level}% (запрошено {level}%)")
                    success_count += 1
                except Exception as e:
                    logger.error(f"ошибка для {monitor}: {e}")

            # Сохраняем старую яркость в историю для отмены
            self.monitor_brightness_history = old_brightness

            if success_count > 0:
                return f"настроил яркость {level}%"
            else:
                return "не получилось настроить яркость"

        except Exception as e:
            logger.error(f"ошибка установки яркости: {e}")
            return "не получилось настроить яркость"

    def restore_previous_brightness(self) -> str:
        """
        Восстанавливает предыдущую яркость для всех мониторов

        Returns:
            str: Результат операции
        """
        try:
            if not self.monitor_brightness_history:
                logger.warning("нет данных о предыдущей яркости")
                return "не могу восстановить предыдущую яркость"

            success_count = 0
            monitors = sbc.list_monitors()

            for monitor in monitors:
                try:
                    if monitor in self.monitor_brightness_history:
                        old_level = self.monitor_brightness_history[monitor]
                        sbc.set_brightness(old_level, display=monitor)
                        logger.info(f"восстановлена яркость для {monitor}: {old_level}%")
                        success_count += 1
                except Exception as e:
                    logger.error(f"ошибка восстановления яркости для {monitor}: {e}")

            if success_count > 0:
                return f"восстановил предыдущую яркость"
            else:
                return "не получилось восстановить яркость"

        except Exception as e:
            logger.error(f"ошибка восстановления яркости: {e}")
            return "не получилось восстановить яркость"

    def brightness_max(self) -> str:
        """
        Устанавливает максимальную яркость

        Returns:
            str: Результат операции
        """
        return self.set_brightness_scaled(100)

    def brightness_min(self) -> str:
        """
        Устанавливает минимальную яркость

        Returns:
            str: Результат операции
        """
        return self.set_brightness_scaled(20)

    def set_brightness_by_level(self, level: int) -> str:
        """
        Устанавливает яркость по числовому значению с записью в историю

        Args:
            level (int): Уровень яркости (0-100)

        Returns:
            str: Результат операции
        """
        # Сохраняем текущую яркость перед изменением
        old_brightness = self.get_current_brightness_for_monitors()

        result = self.set_brightness_scaled(level)

        # Добавляем в историю для возможности отмены
        self.add_to_history(
            "изменение яркости",
            {"old": old_brightness, "new": level},
            lambda: self.restore_previous_brightness()
        )

        return result

    def set_single_monitor(self) -> bool:
        """
        Переключает на один монитор

        Returns:
            bool: True если успешно
        """
        old_mode = self.current_monitor_mode
        try:
            subprocess.run(["DisplaySwitch.exe", "/internal"])
            self.current_monitor_mode = "internal"
            logger.info("переключено на один монитор")

            self.add_to_history(
                "переключение на один монитор",
                {"old_mode": old_mode, "new_mode": "internal"},
                lambda: self.restore_monitor_mode(old_mode)
            )

            return True
        except Exception as e:
            logger.error(f"ошибка переключения мониторов: {e}")
            return False

    def set_extend_monitors(self) -> bool:
        """
        Переключает на режим расширения

        Returns:
            bool: True если успешно
        """
        old_mode = self.current_monitor_mode
        try:
            subprocess.run(["DisplaySwitch.exe", "/extend"])
            self.current_monitor_mode = "extend"
            logger.info("переключено на режим расширения")

            self.add_to_history(
                "переключение на расширение мониторов",
                {"old_mode": old_mode, "new_mode": "extend"},
                lambda: self.restore_monitor_mode(old_mode)
            )

            return True
        except Exception as e:
            logger.error(f"ошибка переключения на расширение: {e}")
            return False

    def set_duplicate_monitors(self) -> bool:
        """
        Переключает на режим дублирования

        Returns:
            bool: True если успешно
        """
        old_mode = self.current_monitor_mode
        try:
            subprocess.run(["DisplaySwitch.exe", "/clone"])
            self.current_monitor_mode = "clone"
            logger.info("переключено на режим дублирования")

            self.add_to_history(
                "переключение на дублирование мониторов",
                {"old_mode": old_mode, "new_mode": "clone"},
                lambda: self.restore_monitor_mode(old_mode)
            )

            return True
        except Exception as e:
            logger.error(f"ошибка переключения на дублирование: {e}")
            return False

    def restore_monitor_mode(self, old_mode: str) -> bool:
        """
        Восстанавливает предыдущий режим монитора

        Args:
            old_mode (str): Предыдущий режим

        Returns:
            bool: True если успешно восстановлено
        """
        if old_mode == "internal":
            return self.set_single_monitor()
        elif old_mode == "extend":
            return self.set_extend_monitors()
        elif old_mode == "clone":
            return self.set_duplicate_monitors()
        return False


# Создаем глобальный экземпляр обработчика
display_handler = DisplayHandler()


# Функции для обратной совместимости
def set_brightness_scaled(level: int) -> str:
    """Обертка для установки яркости"""
    return display_handler.set_brightness_scaled(level)


def set_brightness_by_level(level: int) -> str:
    """Обертка для установки яркости с историей"""
    return display_handler.set_brightness_by_level(level)


def restore_previous_brightness() -> str:
    """Обертка для восстановления яркости"""
    return display_handler.restore_previous_brightness()


def brightness_max() -> str:
    """Обертка для максимальной яркости"""
    return display_handler.brightness_max()


def brightness_min() -> str:
    """Обертка для минимальной яркости"""
    return display_handler.brightness_min()


def set_single_monitor() -> bool:
    """Обертка для переключения на один монитор"""
    return display_handler.set_single_monitor()


def set_extend_monitors() -> bool:
    """Обертка для переключения на расширение"""
    return display_handler.set_extend_monitors()


def set_duplicate_monitors() -> bool:
    """Обертка для переключения на дублирование"""
    return display_handler.set_duplicate_monitors()


def get_current_brightness_for_monitors() -> Dict:
    """Обертка для получения текущей яркости"""
    return display_handler.get_current_brightness_for_monitors()