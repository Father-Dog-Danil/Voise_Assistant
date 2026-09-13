"""
Центральный обработчик команд
Координирует работу всех обработчиков
"""

import logging
from typing import Optional, Tuple, Dict, Any

from handlers.base_handler import BaseHandler, HandlerRegistry, handler_registry, execute_delayed_task
from handlers.program_handler import ProgramHandler
from handlers.audio_handler import AudioHandler
from handlers.display_handler import DisplayHandler
from handlers.window_handler import WindowHandler
from handlers.browser_handler import BrowserHandler
from handlers.system_handler import SystemHandler

from services.logger_service import (
    logger_service,
    log_all_commands,
    log_unknown_command
)

from utils.text_processing import (
    normalize_command,
    extract_brightness_level,
    get_random_response
)

from config import RESPONSES

logger = logging.getLogger(__name__)


class CommandProcessor:
    """
    Центральный обработчик команд
    Управляет всеми обработчиками и маршрутизирует команды
    """

    def __init__(self):
        """Инициализация обработчика команд"""
        self.handlers = []
        self.setup_handlers()
        logger.info(f"инициализирован обработчик команд с {len(self.handlers)} обработчиками")

    def setup_handlers(self):
        """Регистрирует все обработчики"""
        # Порядок важен - сначала специфические, потом общие
        self.handlers = [
            ProgramHandler(),
            AudioHandler(),
            DisplayHandler(),
            WindowHandler(),
            BrowserHandler(),
            SystemHandler()
        ]

        # Регистрируем в глобальном реестре
        for handler in self.handlers:
            handler_registry.register(handler)

    def process_command(self, command: str, original_utterance: str = "") -> str:
        """
        Обрабатывает команду и возвращает ответ

        Args:
            command (str): Команда для обработки
            original_utterance (str): Оригинальная фраза пользователя

        Returns:
            str: Ответ ассистента
        """
        if not command or command.strip() == '':
            return "слушаю вас"

        # Нормализуем команду
        normalized_command = normalize_command(command.lower())

        logger.info(f"обрабатываю команду: {normalized_command}")

        # Специальная обработка для яркости (приоритет)
        brightness_result = self._handle_brightness_command(normalized_command)
        if brightness_result:
            return brightness_result

        # Ищем подходящий обработчик
        immediate_handler, delayed_handler, response_type = self._find_handler(normalized_command)

        response_text = ""

        if immediate_handler or delayed_handler:
            if immediate_handler:
                # Немедленное выполнение
                try:
                    result = immediate_handler()
                    if isinstance(result, str):
                        response_text = result
                    else:
                        response_text = get_random_response(response_type, RESPONSES)
                except Exception as e:
                    logger.error(f"ошибка выполнения немедленного обработчика: {e}")
                    response_text = get_random_response('error', RESPONSES)
            else:
                # Отложенное выполнение
                response_text = get_random_response(response_type, RESPONSES)
                try:
                    delayed_handler()
                except Exception as e:
                    logger.error(f"ошибка запуска отложенного обработчика: {e}")

        # Если не нашли обработчик
        if not response_text:
            logger.info(f"команда не распознана: {normalized_command}")
            log_unknown_command(normalized_command, original_utterance)
            response_text = self._get_unknown_command_response()

        # Логируем команду
        log_all_commands(normalized_command, response_text, original_utterance)

        return response_text

    def _handle_brightness_command(self, command: str) -> Optional[str]:
        """
        Специальная обработка команд яркости

        Args:
            command (str): Команда

        Returns:
            Optional[str]: Ответ или None если не команда яркости
        """
        if any(word in command for word in ['яркость', 'ярко', 'свет']):
            brightness_level = extract_brightness_level(command)
            if brightness_level is not None:
                logger.info(f"устанавливаю яркость: {brightness_level}%")

                from handlers.display_handler import display_handler

                def brightness_task():
                    result = display_handler.set_brightness_by_level(brightness_level)
                    logger.info(f"результат установки яркости: {result}")

                execute_delayed_task(brightness_task)
                return get_random_response('brightness', RESPONSES)

        return None

    def _find_handler(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Находит подходящий обработчик для команды

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Ищем обработчик с наилучшим совпадением
        best_score = 0
        best_handler = None

        for handler in self.handlers:
            score = handler.get_score(command)
            if score > best_score:
                best_score = score
                best_handler = handler

        if best_handler and best_score > 0:
            logger.info(f"выбран обработчик: {best_handler.__class__.__name__} (очки: {best_score})")
            return best_handler.handle(command)

        return None, None, ""

    def _get_unknown_command_response(self) -> str:
        """
        Возвращает ответ для неизвестной команды

        Returns:
            str: Ответ
        """
        import random
        return random.choice([
            "не понял команду, скажите помощь для списка команд",
            "повторите пожалуйста",
            "что сделать"
        ])

    def process_with_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает команду с контекстом (для Flask API)

        Args:
            data (Dict[str, Any]): Данные запроса

        Returns:
            Dict[str, Any]: Ответ в формате API
        """
        command = data.get('request', {}).get('command', '').lower()
        original_utterance = data.get('request', {}).get('original_utterance', '')

        response_text = self.process_command(command, original_utterance)

        return {
            "version": data.get("version", "1.0"),
            "session": data.get("session", {}),
            "response": {
                "text": response_text,
                "end_session": False
            }
        }

    def get_handler_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику по обработчикам

        Returns:
            Dict[str, int]: Статистика
        """
        stats = {}
        for handler in self.handlers:
            stats[handler.__class__.__name__] = len(handler.keywords)
        return stats

    def add_handler(self, handler: BaseHandler):
        """
        Добавляет новый обработчик

        Args:
            handler (BaseHandler): Обработчик для добавления
        """
        if isinstance(handler, BaseHandler):
            self.handlers.append(handler)
            handler_registry.register(handler)
            logger.info(f"добавлен обработчик: {handler.__class__.__name__}")

    def remove_handler(self, handler_class):
        """
        Удаляет обработчик по классу

        Args:
            handler_class: Класс обработчика для удаления
        """
        self.handlers = [h for h in self.handlers if not isinstance(h, handler_class)]
        handler_registry.unregister(handler_class)
        logger.info(f"удален обработчик: {handler_class.__name__}")

    def get_all_handlers(self) -> list:
        """
        Возвращает все обработчики

        Returns:
            list: Список обработчиков
        """
        return self.handlers.copy()


# Создаем глобальный экземпляр
command_processor = CommandProcessor()


# Функции для обратной совместимости
def process_command(command: str, original_utterance: str = "") -> str:
    """
    Обертка для обработки команды

    Args:
        command (str): Команда
        original_utterance (str): Оригинальная фраза

    Returns:
        str: Ответ
    """
    return command_processor.process_command(command, original_utterance)


def find_command_handler(command: str):
    """
    Обертка для поиска обработчика (для совместимости)

    Args:
        command (str): Команда

    Returns:
        Tuple: (немедленный обработчик, отложенный обработчик, тип ответа)
    """
    return command_processor._find_handler(command)


def handle_advanced_commands(command: str) -> Tuple[Optional[callable], Optional[callable], str]:
    """
    Обертка для обработки сложных команд (для совместимости)

    Args:
        command (str): Команда

    Returns:
        Tuple: (немедленный обработчик, отложенный обработчик, тип ответа)
    """
    normalized_command = normalize_command(command)
    return command_processor._find_handler(normalized_command)