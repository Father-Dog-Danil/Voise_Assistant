"""
Обработчик системных команд
Содержит логику для работы с системой
"""

import logging
import subprocess
from datetime import datetime
from typing import Optional, Tuple

import pyautogui

from handlers.base_handler import BaseHandler, execute_delayed_task
from services.logger_service import (
    get_unknown_commands_stats,
    clear_unknown_commands,
    undo_last_action,
    logger_service
)
from services.program_database import program_database

logger = logging.getLogger(__name__)


class SystemHandler(BaseHandler):
    """
    Обработчик для системных команд
    """

    def __init__(self):
        """Инициализация системного обработчика"""
        super().__init__()
        self.keywords = [
            'компьютер', 'система', 'время', 'статистика',
            'помощь', 'отмена', 'обнови', 'заблокируй',
            'выключи', 'перезагрузи', 'сон', 'спящий'
        ]
        self.response_type = 'system'

    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает системную команду

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Блокировка компьютера
        if any(word in command for word in ['заблокируй компьютер', 'заблокируй', 'лок', 'lock', 'блокировка']):
            logger.info("блокирую компьютер")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.lock_computer), self.response_type

        # Выключение компьютера
        if any(word in command for word in
               ['выключи компьютер', 'выключи пк', 'shutdown', 'выключение', 'заверши работу']):
            logger.info("выключаю компьютер")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.shutdown_computer), self.response_type

        # Перезагрузка компьютера
        if any(word in command for word in
               ['перезагрузи компьютер', 'перезагрузка', 'restart', 'ребут', 'reboot', 'перезагрузи пк']):
            logger.info("перезагружаю компьютер")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.restart_computer), self.response_type

        # Отмена выключения
        if any(word in command for word in
               ['отмени выключение', 'отмена выключения', 'не выключай', 'отмени перезагрузку']):
            logger.info("отменяю выключение")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.cancel_shutdown), self.response_type

        # Режим сна
        if any(word in command for word in ['режим сна', 'спящий режим', 'усни', 'sleep', 'сон', 'гибернация']):
            logger.info("перевожу в режим сна")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.sleep_mode), self.response_type

        # Текущее время
        if any(word in command for word in
               ['время', 'который час', 'сколько времени', 'текущее время', 'время сейчас']):
            logger.info("получаю текущее время")
            self.response_type = 'time'
            return self.get_current_time, None, self.response_type

        # Статистика
        if any(word in command for word in ['статистика', 'отчет', 'аналитика', 'непонятые команды', 'лог команд']):
            logger.info("получаю статистику")
            self.response_type = 'stats'
            return get_unknown_commands_stats, None, self.response_type

        # Очистка статистики
        if any(word in command for word in
               ['очисти статистику', 'очистить логи', 'удали историю команд', 'сбросить статистику']):
            logger.info("очищаю статистику")
            self.response_type = 'system'
            return clear_unknown_commands, None, self.response_type

        # Отмена последнего действия
        if any(word in command for word in ['отмена', 'отмени', 'верни назад', 'отмени последнее', 'undo']):
            logger.info("отменяю последнее действие")
            self.response_type = 'undo'
            return undo_last_action, None, self.response_type

        # Обновление базы программ
        if any(word in command for word in
               ['обнови пути', 'обнови программы', 'обновить базу', 'сканируй программы', 'обнови список']):
            logger.info("обновляю базу программ")
            self.response_type = 'update'
            return program_database.update, None, self.response_type

        # Помощь
        if any(word in command for word in
               ['помощь', 'помоги', 'что ты умеешь', 'что еще ты умеешь', 'список команд', 'команды']):
            logger.info("показываю помощь")
            self.response_type = 'help'
            return self.get_commands_list, None, self.response_type

        return None, None, ""

    def lock_computer(self) -> bool:
        """
        Блокирует компьютер

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('win', 'l')
            logger.info("компьютер заблокирован")
            return True
        except Exception as e:
            logger.error(f"ошибка блокировки компьютера: {e}")
            return False

    def shutdown_computer(self) -> bool:
        """
        Выключает компьютер (с задержкой 60 секунд)

        Returns:
            bool: True если команда выполнена
        """
        try:
            subprocess.run(["shutdown", "/s", "/t", "60"])
            logger.info("компьютер будет выключен через 60 секунд")
            return True
        except Exception as e:
            logger.error(f"ошибка выключения компьютера: {e}")
            return False

    def restart_computer(self) -> bool:
        """
        Перезагружает компьютер (с задержкой 60 секунд)

        Returns:
            bool: True если команда выполнена
        """
        try:
            subprocess.run(["shutdown", "/r", "/t", "60"])
            logger.info("компьютер будет перезагружен через 60 секунд")
            return True
        except Exception as e:
            logger.error(f"ошибка перезагрузки компьютера: {e}")
            return False

    def cancel_shutdown(self) -> bool:
        """
        Отменяет выключение/перезагрузку

        Returns:
            bool: True если успешно отменено
        """
        try:
            subprocess.run(["shutdown", "/a"])
            logger.info("выключение отменено")
            return True
        except Exception as e:
            logger.error(f"ошибка отмены выключения: {e}")
            return False

    def sleep_mode(self) -> bool:
        """
        Переводит компьютер в режим сна

        Returns:
            bool: True если успешно
        """
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            logger.info("компьютер переведен в режим сна")
            return True
        except Exception as e:
            logger.error(f"ошибка перевода в режим сна: {e}")
            return False

    def get_current_time(self) -> str:
        """
        Возвращает текущее время

        Returns:
            str: Текущее время
        """
        current_time = datetime.now().strftime("%H:%M")
        logger.info(f"текущее время: {current_time}")
        return f"сейчас {current_time}"

    def get_commands_list(self) -> str:
        """
        Возвращает список всех доступных команд

        Returns:
            str: Список команд
        """
        commands_list = (
            "📋 вот что я умею:\n\n"
            "🎮 запуск программ:\n"
            "• 'запусти телеграм', 'открой телеграм', 'тг'\n"
            "• 'запусти дискорд', 'открой дискорд', 'дс'\n"
            "• 'запусти хром', 'открой хром', 'гугл хром'\n"
            "• 'запусти яндекс', 'открой яндекс браузер'\n"
            "• 'запусти стим', 'открой стим', 'игры'\n"
            "• 'запусти вскод', 'открой вскод', 'вижуал студио код'\n"
            "• 'запусти пайчарм', 'открой пайчарм', 'python'\n"
            "• 'запусти спотифай', 'включи музыку', 'плеер'\n"
            "• 'запусти ворд', 'открой ворд', 'word'\n"
            "• 'обнови пути' - обновить базу данных программ 🆕\n\n"
            "🔊 управление звуком:\n"
            "• 'колонки' - переключить на колонки\n"
            "• 'наушники' - переключить на наушники\n"
            "• 'громче' - увеличить громкость\n"
            "• 'тише' - уменьшить громкость\n"
            "• 'выключи звук' - отключить звук\n"
            "• 'пауза' - пауза/продолжить музыку\n"
            "• 'следующий трек' - следующий трек\n"
            "• 'предыдущий трек' - предыдущий трек\n\n"
            "💡 управление яркостью:\n"
            "• 'яркость 50' - установить яркость 50%\n"
            "• 'яркость 0-100' - любое значение яркости\n"
            "• 'максимальная яркость' - яркость на максимум\n"
            "• 'минимальная яркость' - яркость на минимум\n\n"
            "🖥️ управление мониторами:\n"
            "• 'один монитор' - только основной монитор\n"
            "• 'два монитора' - режим расширения\n"
            "• 'дублировать экран' - одинаковое изображение\n\n"
            "🪟 управление окнами:\n"
            "• 'сверни окна' - свернуть все окна\n"
            "• 'верни окна' - восстановить окна\n"
            "• 'закрой окна' - закрыть все окна (безопасно)\n"
            "• 'рабочий стол' - показать рабочий стол\n\n"
            "🌐 браузер:\n"
            "• 'обнови страницу' - f5\n"
            "• 'новая вкладка' - ctrl+t\n"
            "• 'закрой вкладку' - ctrl+w\n"
            "• 'назад' - alt+left\n"
            "• 'вперед' - alt+right\n"
            "• 'найди котиков' - поиск в интернете\n\n"
            "⚡ системные команды:\n"
            "• 'заблокируй компьютер' - win+l\n"
            "• 'время' - текущее время\n"
            "• 'статистика' - статистика команд\n"
            "• 'очисти статистику' - очистить логи\n"
            "• 'отмена' - отменить последнее действие\n\n"
            "🔄 обновление:\n"
            "• 'обнови пути' - обновить базу программ 🆕\n"
            "• 'обнови программы' - обновить список приложений 🆕\n\n"
            "💡 просто говори команды естественно - я пойму"
        )
        return commands_list


# Создаем глобальный экземпляр обработчика
system_handler = SystemHandler()


# Функции для обратной совместимости
def lock_computer() -> bool:
    """Обертка для блокировки компьютера"""
    return system_handler.lock_computer()


def shutdown_computer() -> bool:
    """Обертка для выключения компьютера"""
    return system_handler.shutdown_computer()


def restart_computer() -> bool:
    """Обертка для перезагрузки компьютера"""
    return system_handler.restart_computer()


def cancel_shutdown() -> bool:
    """Обертка для отмены выключения"""
    return system_handler.cancel_shutdown()


def sleep_mode() -> bool:
    """Обертка для режима сна"""
    return system_handler.sleep_mode()


def get_current_time() -> str:
    """Обертка для получения времени"""
    return system_handler.get_current_time()


def get_commands_list() -> str:
    """Обертка для получения списка команд"""
    return system_handler.get_commands_list()