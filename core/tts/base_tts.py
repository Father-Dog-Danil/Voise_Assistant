"""
Абстрактный базовый класс для всех TTS-движков.

Любой движок (Piper, XTTS, что-то ещё) обязан реализовать
методы speak / stop / is_ready. Остальной код ассистента работает
только через этот интерфейс и не знает, какой движок под капотом.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseTTS(ABC):
    """
    Базовый интерфейс синтеза речи.

    Контракт простой:
      - speak(text) — озвучить текст (блокирующий вызов: вернётся,
        когда речь отыграет до конца);
      - stop()      — остановить текущее воспроизведение и освободить
        ресурсы (вызывается при выходе из ассистента);
      - is_ready()  — готов ли движок принимать текст.
    """

    def __init__(self, settings: dict):
        """
        settings — секция настроек конкретного движка из config.TTS_SETTINGS.
        Например, для Piper это TTS_SETTINGS['piper'], для XTTS — ['xtts'].
        """
        self.settings = settings or {}
        self._ready = False

    @abstractmethod
    def speak(self, text: str) -> bool:
        """
        Озвучивает текст. Возвращает True, если всё прошло успешно.
        Метод блокирующий — управление вернётся только после того,
        как аудио отыграет до конца.
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """
        Останавливает воспроизведение и освобождает ресурсы.
        Должен быть идемпотентным (можно вызывать много раз).
        """
        raise NotImplementedError

    def is_ready(self) -> bool:
        """Готов ли движок к работе. По умолчанию — по флагу _ready."""
        return self._ready

    def warmup(self):
        """
        Необязательный прогрев. По умолчанию ничего не делает.
        Нужен для тяжёлых движков (XTTS), чтобы модель загрузилась заранее.
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __repr__(self):
        return f"{self.__class__.__name__}(ready={self._ready})"