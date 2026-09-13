"""
Модуль синтеза речи (TTS).

Содержит абстрактный базовый класс и реализации движков озвучки.
Активный движок выбирается через config.TTS_SETTINGS['engine'].
"""

from core.tts.base_tts import BaseTTS
from core.tts.tts_factory import create_tts, get_tts

__all__ = ['BaseTTS', 'create_tts', 'get_tts']