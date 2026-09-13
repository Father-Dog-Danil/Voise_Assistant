"""
Обработчик управления браузером
Содержит логику для работы с браузером и поиском
"""

import logging
import subprocess
from typing import Optional, Tuple

import pyautogui

from handlers.base_handler import BaseHandler, execute_delayed_task
from services.program_database import program_database
from utils.text_processing import extract_search_query

logger = logging.getLogger(__name__)


class BrowserHandler(BaseHandler):
    """
    Обработчик для управления браузером
    """

    def __init__(self):
        """Инициализация обработчика браузера"""
        super().__init__()
        self.keywords = [
            'браузер', 'страница', 'вкладка', 'найди', 'поиск',
            'обнови', 'назад', 'вперед', 'яндекс'
        ]
        self.response_type = 'system'

    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает команду управления браузером

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Обновить страницу
        if any(word in command for word in ['обнови страницу', 'обновить', 'релоад', 'reload', 'перезагрузи страницу']):
            logger.info("обновляю страницу")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.browser_refresh), self.response_type

        # Новая вкладка
        if any(word in command for word in
               ['новая вкладка', 'открой вкладку', 'создай вкладку', 'новая таб', 'new tab']):
            logger.info("открываю новую вкладку")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.browser_new_tab), self.response_type

        # Закрыть вкладку
        if any(word in command for word in
               ['закрой вкладку', 'закрыть вкладку', 'удали вкладку', 'close tab', 'закрой таб']):
            logger.info("закрываю вкладку")
            self.response_type = 'close'
            return None, lambda: execute_delayed_task(self.browser_close_tab), self.response_type

        # Назад
        if any(word in command for word in ['назад', 'вернись назад', 'back', 'предыдущая страница', 'верни']):
            logger.info("перехожу назад")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.browser_back), self.response_type

        # Вперед
        if any(word in command for word in ['вперед', 'вперёд', 'forward', 'следующая страница', 'дальше в браузере']):
            logger.info("перехожу вперед")
            self.response_type = 'system'
            return None, lambda: execute_delayed_task(self.browser_forward), self.response_type

        # Поиск в интернете
        if any(word in command for word in ['найди', 'поиск', 'ищи', 'найти', 'поискать', 'искать']):
            search_query = extract_search_query(command)
            if search_query:
                logger.info(f"ищу в интернете: {search_query}")
                self.response_type = 'search'
                return None, lambda: execute_delayed_task(self.search_in_yandex, search_query), self.response_type

        return None, None, ""

    def browser_refresh(self) -> bool:
        """
        Обновляет страницу в браузере

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('f5')
            logger.info("страница обновлена")
            return True
        except Exception as e:
            logger.error(f"ошибка обновления страницы: {e}")
            return False

    def browser_new_tab(self) -> bool:
        """
        Открывает новую вкладку в браузере

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('ctrl', 't')
            logger.info("новая вкладка открыта")
            return True
        except Exception as e:
            logger.error(f"ошибка открытия новой вкладки: {e}")
            return False

    def browser_close_tab(self) -> bool:
        """
        Закрывает текущую вкладку в браузере

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('ctrl', 'w')
            logger.info("вкладка закрыта")
            return True
        except Exception as e:
            logger.error(f"ошибка закрытия вкладки: {e}")
            return False

    def browser_back(self) -> bool:
        """
        Переходит назад в браузере

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('alt', 'left')
            logger.info("переход назад выполнен")
            return True
        except Exception as e:
            logger.error(f"ошибка навигации назад: {e}")
            return False

    def browser_forward(self) -> bool:
        """
        Переходит вперед в браузере

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.hotkey('alt', 'right')
            logger.info("переход вперед выполнен")
            return True
        except Exception as e:
            logger.error(f"ошибка навигации вперед: {e}")
            return False

    def search_in_yandex(self, query: str) -> bool:
        """
        Выполняет поиск в Яндексе

        Args:
            query (str): Поисковый запрос

        Returns:
            bool: True если успешно
        """
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://yandex.ru/search/?text={encoded_query}"
            logger.info(f"ищу в яндекс: {query}")

            # Ищем Яндекс браузер в базе
            program_info = program_database.find_program_by_name("яндекс")
            if program_info:
                exe_path = program_info.get("exe_path", "")
                subprocess.Popen([exe_path, search_url])
                return True
            else:
                logger.error("яндекс браузер не найден в базе данных")
                return False
        except Exception as e:
            logger.error(f"ошибка поиска в яндекс: {e}")
            return False

    def search_in_google(self, query: str) -> bool:
        """
        Выполняет поиск в Google

        Args:
            query (str): Поисковый запрос

        Returns:
            bool: True если успешно
        """
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            logger.info(f"ищу в google: {query}")

            # Ищем Chrome в базе
            program_info = program_database.find_program_by_name("хром")
            if program_info:
                exe_path = program_info.get("exe_path", "")
                subprocess.Popen([exe_path, search_url])
                return True
            else:
                logger.error("chrome не найден в базе данных")
                return False
        except Exception as e:
            logger.error(f"ошибка поиска в google: {e}")
            return False

    def open_url(self, url: str) -> bool:
        """
        Открывает URL в браузере по умолчанию

        Args:
            url (str): URL для открытия

        Returns:
            bool: True если успешно
        """
        try:
            import webbrowser
            webbrowser.open(url)
            logger.info(f"открыт URL: {url}")
            return True
        except Exception as e:
            logger.error(f"ошибка открытия URL: {e}")
            return False


# Создаем глобальный экземпляр обработчика
browser_handler = BrowserHandler()


# Функции для обратной совместимости
def browser_refresh() -> bool:
    """Обертка для обновления страницы"""
    return browser_handler.browser_refresh()


def browser_new_tab() -> bool:
    """Обертка для открытия новой вкладки"""
    return browser_handler.browser_new_tab()


def browser_close_tab() -> bool:
    """Обертка для закрытия вкладки"""
    return browser_handler.browser_close_tab()


def browser_back() -> bool:
    """Обертка для перехода назад"""
    return browser_handler.browser_back()


def browser_forward() -> bool:
    """Обертка для перехода вперед"""
    return browser_handler.browser_forward()


def search_in_yandex(query: str) -> bool:
    """Обертка для поиска в Яндексе"""
    return browser_handler.search_in_yandex(query)


def search_in_google(query: str) -> bool:
    """Обертка для поиска в Google"""
    return browser_handler.search_in_google(query)


def open_url(url: str) -> bool:
    """Обертка для открытия URL"""
    return browser_handler.open_url(url)