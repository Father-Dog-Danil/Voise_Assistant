"""
Утилиты для обработки текста
Содержит функции для работы с текстовыми командами
"""

import re
from typing import Optional
from config import WAKE_WORDS, FILLER_WORDS, NUMERALS


def contains_wake_word(text: str) -> bool:
    """
    Проверяет содержит ли текст обращение к ассистенту

    Args:
        text (str): Текст для проверки

    Returns:
        bool: True если содержит обращение, False если нет
    """
    if not text:
        return False

    text_lower = text.lower().strip()

    # Проверяем начало строки на обращение
    for wake_word in WAKE_WORDS:
        # Проверяем если строка начинается с обращения
        if text_lower.startswith(wake_word):
            return True
        # Проверяем если обращение стоит после запятой или в начале
        if re.search(rf'(?:^|[,\s]){wake_word}(?:[,\s]|$)', text_lower):
            return True

    return False


def extract_command_without_wake_word(text: str) -> str:
    """
    Извлекает команду без обращения к ассистенту

    Args:
        text (str): Исходный текст с обращением

    Returns:
        str: Команда без обращения и слов-паразитов
    """
    if not text:
        return ""

    text_lower = text.lower().strip()

    # Находим и удаляем обращение к ассистенту
    for wake_word in sorted(WAKE_WORDS, key=len, reverse=True):
        # Удаляем обращение в начале строки
        if text_lower.startswith(wake_word):
            text_lower = text_lower[len(wake_word):].strip()
            break
        # Удаляем обращение после запятой
        text_lower = re.sub(rf'^[,\s]*{wake_word}[,\s]*', '', text_lower)
        # Удаляем обращение в начале с запятой
        text_lower = re.sub(rf'^{wake_word}[,\s]+', '', text_lower)

    # Очищаем от начальных знаков препинания
    text_lower = re.sub(r'^[,\s.]+', '', text_lower)

    # Удаляем слова-паразиты
    for filler in FILLER_WORDS:
        text_lower = re.sub(rf'\b{filler}\b', '', text_lower)

    # Очищаем от лишних пробелов
    text_lower = ' '.join(text_lower.split())

    return text_lower


def normalize_command(command: str) -> str:
    """
    Нормализует команду: заменяет числительные, убирает лишнее

    Args:
        command (str): Исходная команда

    Returns:
        str: Нормализованная команда
    """
    if not command:
        return ""

    # Заменяем числительные на цифры
    for word, digit in NUMERALS.items():
        command = command.replace(word, digit)

    # Убираем лишние пробелы
    command = ' '.join(command.split())

    return command


def extract_app_name(command: str) -> str:
    """
    Извлекает название приложения из команды

    Args:
        command (str): Команда

    Returns:
        str: Название приложения
    """
    stop_words = ['запусти', 'мне', 'пожалуйста', 'открой', 'включи', 'яндекс']
    words = command.split()
    app_words = [word for word in words if word not in stop_words]
    return ' '.join(app_words).strip()


def extract_search_query(command: str) -> str:
    """
    Извлекает поисковый запрос из команды

    Args:
        command (str): Команда

    Returns:
        str: Поисковый запрос
    """
    stop_words = ['найди', 'поиск', 'ищи', 'найти', 'яндекс']
    words = command.split()
    query_words = [word for word in words if word not in stop_words]
    return ' '.join(query_words).strip()


def extract_type_text(command: str) -> str:
    """
    Извлекает текст для ввода из команды

    Args:
        command (str): Команда

    Returns:
        str: Текст для ввода
    """
    stop_words = ['ввод', 'введи', 'напиши', 'вот', 'введите', 'печатай']
    words = command.split()
    text_words = [word for word in words if word not in stop_words]
    return ' '.join(text_words).strip()


def extract_brightness_level(command: str, current_brightness_dict: Optional[dict] = None) -> Optional[int]:
    """
    Извлекает уровень яркости из команды

    Args:
        command (str): Команда
        current_brightness_dict (dict, optional): Текущая яркость мониторов

    Returns:
        Optional[int]: Уровень яркости (0-100) или None
    """
    # Ищем числа в команде
    numbers = re.findall(r'\b(\d{1,3})\b', command)
    if numbers:
        level = int(numbers[0])
        if 0 <= level <= 100:
            return level

    # Проверяем ключевые слова для максимума/минимума
    if any(word in command for word in ['максимум', 'максимальная', 'полная', 'сто']):
        return 100
    elif any(word in command for word in ['минимум', 'минимальная', 'ноль', 'нулевая']):
        return 0
    elif any(word in command for word in ['понизь', 'уменьши', 'убавь']):
        # Уменьшаем яркость
        if current_brightness_dict:
            avg_brightness = sum(current_brightness_dict.values()) / len(current_brightness_dict)
            return max(0, int(avg_brightness) - 30)
        else:
            return 50  # Значение по умолчанию
    elif any(word in command for word in ['повысь', 'увеличь', 'добавь']):
        # Увеличиваем яркость
        if current_brightness_dict:
            avg_brightness = sum(current_brightness_dict.values()) / len(current_brightness_dict)
            return min(100, int(avg_brightness) + 30)
        else:
            return 50  # Значение по умолчанию

    return None


def get_random_response(category: str, responses_dict: dict) -> str:
    """
    Возвращает случайный ответ из категории

    Args:
        category (str): Категория ответа
        responses_dict (dict): Словарь ответов

    Returns:
        str: Случайный ответ
    """
    import random
    return random.choice(responses_dict.get(category, responses_dict.get('success', ['сделал'])))


def clean_text(text: str) -> str:
    """
    Очищает текст от лишних символов и пробелов

    Args:
        text (str): Исходный текст

    Returns:
        str: Очищенный текст
    """
    if not text:
        return ""

    # Убираем лишние пробелы
    text = ' '.join(text.split())

    # Убираем множественные знаки препинания
    text = re.sub(r'([,.!?])\1+', r'\1', text)

    return text.strip()


def is_similar_text(text1: str, text2: str, threshold: float = 0.8) -> bool:
    """
    Проверяет похожесть двух текстов (простая реализация)

    Args:
        text1 (str): Первый текст
        text2 (str): Второй текст
        threshold (float): Порог похожести (0-1)

    Returns:
        bool: True если тексты похожи
    """
    if not text1 or not text2:
        return False

    # Простая проверка на вхождение
    if text1.lower() in text2.lower() or text2.lower() in text1.lower():
        return True

    # Считаем процент совпадающих слов
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return False

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    similarity = len(intersection) / len(union)

    return similarity >= threshold