"""
Сервис логирования
Содержит функции для записи логов команд и действий
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

from config import (
    LOG_FILES_DIR,
    ALL_COMMANDS_FILE,
    UNKNOWN_COMMANDS_FILE,
    ACTION_HISTORY_FILE
)

# Настройка логирования
logger = logging.getLogger(__name__)


class LoggerService:
    """
    Сервис для логирования команд и действий ассистента
    """

    def __init__(self):
        """Инициализация сервиса логирования"""
        self.setup_logging()
        self.action_history = []
        self.load_action_history()

    def setup_logging(self):
        """Настраивает логирование"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(
                    os.path.join(LOG_FILES_DIR, 'yuriy_assistant.log'),
                    encoding='utf-8'
                ),
                logging.StreamHandler()
            ]
        )

    def log_all_commands(self, command: str, response: str, original_utterance: str = ""):
        """
        Записывает все команды и ответы в файл

        Args:
            command (str): Обработанная команда
            response (str): Ответ ассистента
            original_utterance (str): Оригинальная фраза пользователя
        """
        try:
            if not command or command.strip() == '':
                return

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(ALL_COMMANDS_FILE, 'a', encoding='utf-8') as f:
                if original_utterance and original_utterance != command:
                    f.write(
                        f"{timestamp} | запрос: '{command}' | оригинал: '{original_utterance}' | ответ: '{response}'\n")
                else:
                    f.write(f"{timestamp} | запрос: '{command}' | ответ: '{response}'\n")

            logger.info(f"📝 записана команда в лог: {command} -> {response}")

        except Exception as e:
            logger.error(f"ошибка записи команды в лог: {e}")

    def log_unknown_command(self, command: str, original_utterance: str = ""):
        """
        Записывает непонятую команду в файл

        Args:
            command (str): Непонятая команда
            original_utterance (str): Оригинальная фраза пользователя
        """
        try:
            if not command or command.strip() == '':
                return

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(UNKNOWN_COMMANDS_FILE, 'a', encoding='utf-8') as f:
                if original_utterance and original_utterance != command:
                    f.write(f"{timestamp} | '{command}' | оригинал: '{original_utterance}'\n")
                else:
                    f.write(f"{timestamp} | '{command}'\n")

            logger.info(f"📝 записана непонятая команда: {command}")

        except Exception as e:
            logger.error(f"ошибка записи непонятой команды: {e}")

    def get_unknown_commands_stats(self) -> str:
        """
        Показывает статистику по непонятым командам

        Returns:
            str: Статистика в текстовом формате
        """
        try:
            if not os.path.exists(UNKNOWN_COMMANDS_FILE):
                return "файл с непонятыми командами пуст"

            with open(UNKNOWN_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                return "файл с непонятыми командами пуст"

            command_count = {}
            for line in lines:
                parts = line.split('|')
                if len(parts) >= 2:
                    cmd = parts[1].strip().strip("'")
                    if cmd:
                        command_count[cmd] = command_count.get(cmd, 0) + 1

            sorted_commands = sorted(command_count.items(), key=lambda x: x[1], reverse=True)

            stats = "📊 статистика непонятых команд:\n"
            for cmd, count in sorted_commands[:10]:
                stats += f"  '{cmd}' - {count} раз(а)\n"

            stats += f"\nвсего уникальных команд: {len(sorted_commands)}"
            return stats

        except Exception as e:
            return f"ошибка получения статистики: {e}"

    def clear_unknown_commands(self) -> str:
        """
        Очищает файл с непонятыми командами

        Returns:
            str: Результат операции
        """
        try:
            if os.path.exists(UNKNOWN_COMMANDS_FILE):
                os.remove(UNKNOWN_COMMANDS_FILE)
                logger.info("файл с непонятыми командами очищен")
                return "файл с непонятыми командами очищен"
            else:
                return "файл с непонятыми командами не существует"
        except Exception as e:
            logger.error(f"ошибка очистки файла: {e}")
            return f"ошибка очистки: {e}"

    def load_action_history(self):
        """
        Загружает историю действий из файла
        """
        try:
            if os.path.exists(ACTION_HISTORY_FILE):
                with open(ACTION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        self.action_history = []
                        return

                    loaded_data = json.loads(content)
                    self.action_history = [
                        item for item in loaded_data
                        if isinstance(item, dict) and 'type' in item
                    ]
                logger.info(f"загружено {len(self.action_history)} действий из истории")
            else:
                self.action_history = []
        except Exception as e:
            logger.error(f"ошибка загрузки истории действий: {e}")
            self.action_history = []
            try:
                with open(ACTION_HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            except:
                pass

    def save_action_history(self):
        """
        Сохраняет историю действий в файл
        """
        try:
            serializable_history = []
            for action in self.action_history:
                # Сохраняем только сериализуемые данные
                serializable_action = {
                    'type': action.get('type', ''),
                    'details': action.get('details', {}),
                    'timestamp': action.get('timestamp', ''),
                }
                # Убираем функции из сохранения
                if 'reverse_action' in action:
                    serializable_action['has_reverse_action'] = True
                serializable_history.append(serializable_action)

            with open(ACTION_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"ошибка сохранения истории действий: {e}")

    def add_to_history(self, action_type: str, details: dict, reverse_action: callable):
        """
        Добавляет действие в историю

        Args:
            action_type (str): Тип действия
            details (dict): Детали действия
            reverse_action (callable): Функция для отмены действия
        """
        from config import MAX_HISTORY_SIZE

        action = {
            'type': action_type,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'reverse_action': reverse_action
        }

        self.action_history.append(action)

        if len(self.action_history) > MAX_HISTORY_SIZE:
            self.action_history = self.action_history[-MAX_HISTORY_SIZE:]

        self.save_action_history()
        logger.info(f"добавлено в историю: {action_type}")

    def undo_last_action(self) -> str:
        """
        Отменяет последнее действие

        Returns:
            str: Результат отмены
        """
        if not self.action_history:
            return "нет действий для отмены"

        last_action = self.action_history.pop()
        self.save_action_history()

        try:
            if 'reverse_action' in last_action and callable(last_action['reverse_action']):
                result = last_action['reverse_action']()
                logger.info(f"отменено действие: {last_action['type']}")
                return f"отменил: {last_action['type']}"
            else:
                return "не могу отменить это действие"
        except Exception as e:
            logger.error(f"ошибка отмены действия: {e}")
            return f"не получилось отменить действие"

    def get_action_history(self) -> List[Dict]:
        """
        Возвращает историю действий

        Returns:
            List[Dict]: История действий
        """
        return self.action_history.copy()

    def clear_action_history(self):
        """
        Очищает историю действий
        """
        self.action_history = []
        self.save_action_history()
        logger.info("история действий очищена")

    def get_recent_commands(self, limit: int = 10) -> List[str]:
        """
        Возвращает последние команды из лога

        Args:
            limit (int): Количество команд

        Returns:
            List[str]: Список последних команд
        """
        try:
            if not os.path.exists(ALL_COMMANDS_FILE):
                return []

            with open(ALL_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Берем последние N строк
            recent_lines = lines[-limit:] if len(lines) > limit else lines

            commands = []
            for line in recent_lines:
                parts = line.split('|')
                if len(parts) >= 2:
                    commands.append(parts[1].strip())

            return commands
        except Exception as e:
            logger.error(f"ошибка получения последних команд: {e}")
            return []

    def get_log_file_size(self) -> Optional[int]:
        """
        Возвращает размер файла логов

        Returns:
            Optional[int]: Размер файла в байтах
        """
        try:
            if os.path.exists(ALL_COMMANDS_FILE):
                return os.path.getsize(ALL_COMMANDS_FILE)
            return 0
        except Exception as e:
            logger.error(f"ошибка получения размера файла логов: {e}")
            return None

    def clear_all_logs(self) -> str:
        """
        Очищает все логи

        Returns:
            str: Результат операции
        """
        try:
            files_to_clear = [ALL_COMMANDS_FILE, UNKNOWN_COMMANDS_FILE]

            for file_path in files_to_clear:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"файл очищен: {file_path}")

            # Очищаем историю действий
            self.clear_action_history()

            return "все логи очищены"
        except Exception as e:
            logger.error(f"ошибка очистки логов: {e}")
            return f"ошибка очистки: {e}"


# Создаем глобальный экземпляр для использования
logger_service = LoggerService()


# Функции для обратной совместимости (можно использовать как раньше)
def log_all_commands(command: str, response: str, original_utterance: str = ""):
    """Обертка для логирования команд"""
    logger_service.log_all_commands(command, response, original_utterance)


def log_unknown_command(command: str, original_utterance: str = ""):
    """Обертка для логирования непонятых команд"""
    logger_service.log_unknown_command(command, original_utterance)


def get_unknown_commands_stats() -> str:
    """Обертка для получения статистики"""
    return logger_service.get_unknown_commands_stats()


def clear_unknown_commands() -> str:
    """Обертка для очистки непонятых команд"""
    return logger_service.clear_unknown_commands()


def add_to_history(action_type: str, details: dict, reverse_action: callable):
    """Обертка для добавления в историю"""
    logger_service.add_to_history(action_type, details, reverse_action)


def undo_last_action() -> str:
    """Обертка для отмены последнего действия"""
    return logger_service.undo_last_action()