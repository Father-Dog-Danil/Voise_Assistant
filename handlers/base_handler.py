"""
Базовый класс обработчика команд
Все обработчики наследуются от этого класса
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """
    Базовый класс для всех обработчиков команд

    Attributes:
        keywords (list): Список ключевых слов для определения команды
        immediate_handler (callable): Функция для немедленного выполнения
        delayed_handler (callable): Функция для отложенного выполнения
        response_type (str): Тип ответа из RESPONSES
    """

    def __init__(self):
        """Инициализация обработчика"""
        self.keywords = []
        self.immediate_handler = None
        self.delayed_handler = None
        self.response_type = 'success'

    @abstractmethod
    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает команду

        Args:
            command (str): Команда для обработки

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        pass

    def matches(self, command: str) -> bool:
        """
        Проверяет, подходит ли команда для этого обработчика

        Args:
            command (str): Команда

        Returns:
            bool: True если обработчик подходит
        """
        if not command:
            return False

        command_lower = command.lower()

        # Проверяем по ключевым словам
        for keyword in self.keywords:
            if keyword in command_lower:
                return True

        return False

    def get_score(self, command: str) -> int:
        """
        Возвращает оценку соответствия команды обработчику

        Args:
            command (str): Команда

        Returns:
            int: Оценка (чем выше, тем лучше соответствие)
        """
        if not command:
            return 0

        command_lower = command.lower()
        score = 0

        for keyword in self.keywords:
            if keyword in command_lower:
                score += 1
                # Точное совпадение дает больше очков
                if command_lower == keyword:
                    score += 2

        return score

    def execute_immediate(self, *args, **kwargs) -> Any:
        """
        Выполняет немедленный обработчик

        Returns:
            Any: Результат выполнения
        """
        if self.immediate_handler and callable(self.immediate_handler):
            try:
                logger.info(f"выполняю немедленный обработчик: {self.__class__.__name__}")
                return self.immediate_handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"ошибка выполнения немедленного обработчика: {e}")
                return None
        return None

    def execute_delayed(self, *args, **kwargs) -> bool:
        """
        Запускает отложенный обработчик

        Returns:
            bool: True если обработчик запущен
        """
        if self.delayed_handler and callable(self.delayed_handler):
            try:
                logger.info(f"запускаю отложенный обработчик: {self.__class__.__name__}")
                self.delayed_handler(*args, **kwargs)
                return True
            except Exception as e:
                logger.error(f"ошибка запуска отложенного обработчика: {e}")
                return False
        return False

    def get_response_text(self, responses_dict: Dict) -> str:
        """
        Возвращает случайный ответ из категории

        Args:
            responses_dict (Dict): Словарь ответов

        Returns:
            str: Случайный ответ
        """
        import random
        from config import RESPONSES

        responses = responses_dict or RESPONSES
        return random.choice(responses.get(self.response_type, responses.get('success', ['сделал'])))

    def add_to_history(self, action_type: str, details: dict, reverse_action: callable):
        """
        Добавляет действие в историю

        Args:
            action_type (str): Тип действия
            details (dict): Детали действия
            reverse_action (callable): Функция для отмены
        """
        from services.logger_service import add_to_history
        add_to_history(action_type, details, reverse_action)

    def log_command(self, command: str, response: str, original_utterance: str = ""):
        """
        Логирует команду

        Args:
            command (str): Команда
            response (str): Ответ
            original_utterance (str): Оригинальная фраза
        """
        from services.logger_service import log_all_commands
        log_all_commands(command, response, original_utterance)

    def log_unknown(self, command: str, original_utterance: str = ""):
        """
        Логирует непонятую команду

        Args:
            command (str): Команда
            original_utterance (str): Оригинальная фраза
        """
        from services.logger_service import log_unknown_command
        log_unknown_command(command, original_utterance)

    def __str__(self) -> str:
        """Строковое представление обработчика"""
        return f"{self.__class__.__name__}(keywords={self.keywords})"

    def __repr__(self) -> str:
        """Представление для отладки"""
        return self.__str__()


class DelayedTask:
    """
    Класс для отложенного выполнения задач
    """

    def __init__(self, func: callable, *args, **kwargs):
        """
        Инициализация отложенной задачи

        Args:
            func (callable): Функция для выполнения
            *args: Аргументы функции
            **kwargs: Именованные аргументы функции
        """
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.delay = kwargs.pop('delay', 0.5)  # Задержка перед выполнением

    def execute(self):
        """Выполняет задачу в отдельном потоке"""
        import threading
        import time

        def delayed_execution():
            time.sleep(self.delay)
            try:
                result = self.func(*self.args, **self.kwargs)
                logger.info(f"✅ отложенная задача выполнена: {self.func.__name__}")
                return result
            except Exception as e:
                logger.error(f"❌ ошибка в отложенной задаче {self.func.__name__}: {e}")
                return None

        thread = threading.Thread(target=delayed_execution)
        thread.daemon = True
        thread.start()
        return thread


def execute_delayed_task(task_func: callable, *args, **kwargs):
    """
    Выполняет задачу в отдельном потоке с задержкой

    Args:
        task_func (callable): Функция для выполнения
        *args: Аргументы функции
        **kwargs: Именованные аргументы функции
    """
    task = DelayedTask(task_func, *args, **kwargs)
    return task.execute()


class HandlerRegistry:
    """
    Реестр обработчиков команд
    """

    def __init__(self):
        """Инициализация реестра"""
        self.handlers = []

    def register(self, handler: BaseHandler):
        """
        Регистрирует обработчик

        Args:
            handler (BaseHandler): Обработчик для регистрации
        """
        if isinstance(handler, BaseHandler):
            self.handlers.append(handler)
            logger.info(f"зарегистрирован обработчик: {handler.__class__.__name__}")
        else:
            logger.error(f"попытка зарегистрировать не обработчик: {type(handler)}")

    def unregister(self, handler_class):
        """
        Удаляет обработчик из реестра

        Args:
            handler_class: Класс обработчика для удаления
        """
        self.handlers = [h for h in self.handlers if not isinstance(h, handler_class)]

    def find_best_handler(self, command: str) -> Optional[BaseHandler]:
        """
        Находит лучший обработчик для команды

        Args:
            command (str): Команда

        Returns:
            Optional[BaseHandler]: Лучший обработчик или None
        """
        best_handler = None
        best_score = 0

        for handler in self.handlers:
            score = handler.get_score(command)
            if score > best_score:
                best_score = score
                best_handler = handler

        if best_handler and best_score > 0:
            logger.info(f"выбран обработчик: {best_handler.__class__.__name__} (очки: {best_score})")

        return best_handler

    def get_all_handlers(self) -> list:
        """
        Возвращает все зарегистрированные обработчики

        Returns:
            list: Список обработчиков
        """
        return self.handlers.copy()

    def clear(self):
        """Очищает реестр обработчиков"""
        self.handlers = []
        logger.info("реестр обработчиков очищен")


# Создаем глобальный реестр
handler_registry = HandlerRegistry()