"""
Обработчик управления звуком
Содержит логику для работы с аудиоустройствами и громкостью
"""

import logging
import subprocess
from typing import Optional, Tuple

import pyautogui

from handlers.base_handler import BaseHandler, execute_delayed_task
from config import CONFIG

logger = logging.getLogger(__name__)


class AudioHandler(BaseHandler):
    """
    Обработчик для управления звуком
    """

    def __init__(self):
        """Инициализация обработчика звука"""
        super().__init__()
        self.keywords = [
            'колонки', 'наушники', 'громче', 'тише', 'звук',
            'громкость', 'мут', 'без звука', 'пауза', 'трек',
            'музыка', 'плеер', 'спотифай'
        ]
        self.response_type = 'audio'
        self.current_volume_state = "normal"

    def handle(self, command: str) -> Tuple[Optional[callable], Optional[callable], str]:
        """
        Обрабатывает команду управления звуком

        Args:
            command (str): Команда

        Returns:
            Tuple[Optional[callable], Optional[callable], str]:
                (немедленный обработчик, отложенный обработчик, тип ответа)
        """
        # Переключение на колонки
        if any(word in command for word in ['колонк', 'динамик', 'станция', 'спикер', 'нвидиа', 'broadcast']):
            logger.info("переключаю звук на колонки")
            self.response_type = 'audio'
            return None, lambda: execute_delayed_task(self.set_sound_speakers), self.response_type

        # Переключение на наушники
        if any(word in command for word in ['наушник', 'гарнитур', 'головные', 'уши', 'г435', 'беспроводные']):
            logger.info("переключаю звук на наушники")
            self.response_type = 'audio'
            return None, lambda: execute_delayed_task(self.set_sound_headphones), self.response_type

        # Увеличение громкости
        if any(word in command for word in ['громче', 'увеличить громкость', 'добавь громкости', 'погромче']):
            logger.info("увеличиваю громкость")
            self.response_type = 'volume'
            return None, lambda: execute_delayed_task(self.volume_up), self.response_type

        # Уменьшение громкости
        if any(word in command for word in ['тише', 'уменьшить громкость', 'убавь громкость', 'потише']):
            logger.info("уменьшаю громкость")
            self.response_type = 'volume'
            return None, lambda: execute_delayed_task(self.volume_down), self.response_type

        # Выключение звука
        if any(word in command for word in ['выключи звук', 'мут', 'без звука', 'отключи звук', 'тишина']):
            logger.info("выключаю звук")
            self.response_type = 'volume'
            return None, lambda: execute_delayed_task(self.volume_mute), self.response_type

        # Включение звука
        if any(word in command for word in ['включи звук', 'размут', 'со звуком', 'верни звук']):
            logger.info("включаю звук")
            self.response_type = 'volume'
            return None, lambda: execute_delayed_task(self.volume_mute), self.response_type

        # Пауза/воспроизведение
        if any(word in command for word in ['пауза', 'стоп', 'останови', 'продолжить', 'плей', 'плэй']):
            logger.info("управляю воспроизведением")
            self.response_type = 'media'
            return None, lambda: execute_delayed_task(self.media_play_pause), self.response_type

        # Следующий трек
        if any(word in command for word in ['следующий трек', 'следующая песня', 'дальше', 'некст', 'next']):
            logger.info("переключаю на следующий трек")
            self.response_type = 'media'
            return None, lambda: execute_delayed_task(self.media_next), self.response_type

        # Предыдущий трек
        if any(word in command for word in ['предыдущий трек', 'предыдущая песня', 'назад', 'превиус', 'previous']):
            logger.info("переключаю на предыдущий трек")
            self.response_type = 'media'
            return None, lambda: execute_delayed_task(self.media_previous), self.response_type

        return None, None, ""

    def set_sound_speakers(self) -> bool:
        """
        Переключает звук на колонки

        Returns:
            bool: True если успешно переключено
        """
        logger.info("переключаю звук на колонки")

        old_state = self.get_current_audio_device()

        speakers_config = CONFIG['audio_devices']['speakers']
        success_playback = self.set_audio_device_by_id(speakers_config['playback'], "playback")
        success_recording = self.set_audio_device_by_id(speakers_config['recording'], "recording")

        if success_playback and success_recording:
            self.add_to_history(
                "переключение звука на колонки",
                {"old_state": old_state, "new_state": "speakers"},
                lambda: self.restore_audio_state(old_state)
            )
            logger.info("звук переключен на колонки")
            return True
        else:
            logger.error("ошибка переключения на колонки")
            return False

    def set_sound_headphones(self) -> bool:
        """
        Переключает звук на наушники

        Returns:
            bool: True если успешно переключено
        """
        logger.info("переключаю звук на наушники")

        old_state = self.get_current_audio_device()

        headphones_config = CONFIG['audio_devices']['headphones']
        success_playback = self.set_audio_device_by_id(headphones_config['playback'], "playback")
        success_recording = self.set_audio_device_by_id(headphones_config['recording'], "recording")

        if success_playback and success_recording:
            self.add_to_history(
                "переключение звука на наушники",
                {"old_state": old_state, "new_state": "headphones"},
                lambda: self.restore_audio_state(old_state)
            )
            logger.info("звук переключен на наушники")
            return True
        else:
            logger.error("ошибка переключения на наушники")
            return False

    def get_current_audio_device(self) -> str:
        """
        Получает текущее аудиоустройство

        Returns:
            str: Название текущего устройства
        """
        try:
            ps_command = '''
                Get-Module -ListAvailable -Name AudioDeviceCmdlets | Import-Module
                Write-Output "Playback: $((Get-AudioDevice -Playback).Name)"
            '''
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='cp866'
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"

    def restore_audio_state(self, old_state: str) -> bool:
        """
        Восстанавливает предыдущее состояние звука

        Args:
            old_state (str): Предыдущее состояние

        Returns:
            bool: True если успешно восстановлено
        """
        if "speakers" in old_state.lower():
            return self.set_sound_speakers()
        elif "headphones" in old_state.lower():
            return self.set_sound_headphones()
        return False

    def set_audio_device_by_id(self, device_id: str, device_type: str = "playback") -> bool:
        """
        Устанавливает аудиоустройство по ID

        Args:
            device_id (str): ID устройства
            device_type (str): Тип устройства (playback/recording)

        Returns:
            bool: True если успешно установлено
        """
        try:
            ps_command = f'''
                Get-Module -ListAvailable -Name AudioDeviceCmdlets | Import-Module
                Set-AudioDevice -ID "{device_id}"
            '''
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='cp866'
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"ошибка установки устройства: {e}")
            return False

    def volume_up(self) -> bool:
        """
        Увеличивает громкость

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.press('volumeup')
            logger.info("громкость увеличена")
            return True
        except Exception as e:
            logger.error(f"ошибка увеличения громкости: {e}")
            return False

    def volume_down(self) -> bool:
        """
        Уменьшает громкость

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.press('volumedown')
            logger.info("громкость уменьшена")
            return True
        except Exception as e:
            logger.error(f"ошибка уменьшения громкости: {e}")
            return False

    def volume_mute(self) -> bool:
        """
        Включает/выключает звук

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.press('volumemute')
            logger.info("звук переключен (mute/unmute)")
            return True
        except Exception as e:
            logger.error(f"ошибка переключения звука: {e}")
            return False

    def media_play_pause(self) -> bool:
        """
        Пауза/воспроизведение медиа

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.press('playpause')
            logger.info("управление воспроизведением выполнено")
            return True
        except Exception as e:
            logger.error(f"ошибка управления воспроизведением: {e}")
            return False

    def media_next(self) -> bool:
        """
        Следующий трек

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.press('nexttrack')
            logger.info("переключение на следующий трек")
            return True
        except Exception as e:
            logger.error(f"ошибка переключения трека: {e}")
            return False

    def media_previous(self) -> bool:
        """
        Предыдущий трек

        Returns:
            bool: True если успешно
        """
        try:
            pyautogui.press('prevtrack')
            logger.info("переключение на предыдущий трек")
            return True
        except Exception as e:
            logger.error(f"ошибка переключения на предыдущий трек: {e}")
            return False


# Создаем глобальный экземпляр обработчика
audio_handler = AudioHandler()


# Функции для обратной совместимости
def set_sound_speakers() -> bool:
    """Обертка для переключения на колонки"""
    return audio_handler.set_sound_speakers()


def set_sound_headphones() -> bool:
    """Обертка для переключения на наушники"""
    return audio_handler.set_sound_headphones()


def volume_up() -> bool:
    """Обертка для увеличения громкости"""
    return audio_handler.volume_up()


def volume_down() -> bool:
    """Обертка для уменьшения громкости"""
    return audio_handler.volume_down()


def volume_mute() -> bool:
    """Обертка для переключения звука"""
    return audio_handler.volume_mute()


def media_play_pause() -> bool:
    """Обертка для паузы/воспроизведения"""
    return audio_handler.media_play_pause()


def media_next() -> bool:
    """Обертка для следующего трека"""
    return audio_handler.media_next()


def media_previous() -> bool:
    """Обертка для предыдущего трека"""
    return audio_handler.media_previous()