"""
Фабрика TTS-движков.

Читает config.TTS_SETTINGS['engine'], создаёт нужный движок
и отдаёт его всем, кто просит. Синглтон: движок один на процесс,
потому что XTTS стартует долго и держать два экземпляра бессмысленно.

Если движок не смог запуститься — об этом уже сообщил он сам
(конкретная причина в консоли и в логе). Фабрика просто возвращает
то, что получилось, или None. Никаких автоматических подмен.
"""

import logging
from typing import Optional

from core.tts.base_tts import BaseTTS
from core.tts.piper_tts import PiperTTS
from core.tts.xtts_tts import XttsTTS

logger = logging.getLogger(__name__)

_instance: Optional[BaseTTS] = None


def create_tts(engine: str, tts_settings: dict,
               models_dir: str, base_dir: str) -> Optional[BaseTTS]:
    """Создаёт движок по имени."""
    engine = (engine or '').lower()

    if engine == 'piper':
        cfg = tts_settings.get('piper', {})
        return PiperTTS(cfg, models_dir=models_dir, base_dir=base_dir)

    if engine == 'xtts':
        cfg = tts_settings.get('xtts', {})
        return XttsTTS(cfg, base_dir=base_dir)

    logger.error(f"неизвестный TTS-движок в конфиге: {engine}")
    print(f"❌ неизвестный TTS-движок в конфиге: {engine}")
    return None


def get_tts() -> Optional[BaseTTS]:
    """
    Возвращает активный TTS-движок, создавая его при первом вызове.

    Логика простая:
      1. Если движок уже создан — вернуть его.
      2. Прочитать config.TTS_SETTINGS['engine'].
      3. Создать движок.
      4. Вернуть его или None.
    """
    global _instance

    if _instance is not None:
        return _instance

    # Импорт внутри функции — чтобы не тянуть config при импорте пакета
    from config import TTS_SETTINGS, MODELS_DIR, BASE_DIR

    engine = TTS_SETTINGS.get('engine', 'piper')
    logger.info(f"создаю TTS-движок: {engine}")

    tts = create_tts(engine, TTS_SETTINGS, models_dir=MODELS_DIR, base_dir=BASE_DIR)

    if tts is None:
        logger.error("TTS-движок не создан")
        return None

    _instance = tts
    return _instance


def reset_tts():
    """Сбрасывает синглтон. Нужно при переключении движка на лету."""
    global _instance
    if _instance is not None:
        try:
            _instance.stop()
        except Exception:
            pass
    _instance = None