"""
Голосовой ассистент.

Содержит логику распознавания (Whisper) и синтеза речи (TTS).
Синтез делегируется в core.tts — какой именно движок работает
(Piper или XTTS), решает фабрика на основе config.TTS_SETTINGS.

Экземпляр ассистента создаётся лениво через get_voice_assistant().
Раньше объект создавался прямо при импорте модуля — это приводило
к двойной инициализации Whisper и TTS.
"""

import os
import time
import logging
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import (
    WHISPER_SETTINGS,
    AUDIO_SETTINGS,
)
from core.command_processor import command_processor
from core.tts import get_tts
from utils.text_processing import contains_wake_word, extract_command_without_wake_word

logger = logging.getLogger(__name__)


class VoiceAssistant:
    """
    Голосовой ассистент Юрий.

    Отвечает за две вещи:
      1. Слушать микрофон и распознавать речь через Whisper.
      2. Озвучивать ответы через выбранный TTS-движок.
    """

    def __init__(self):
        print("🔄 инициализация голосового ассистента")

        # Whisper
        print("📥 загрузка whisper (распознавание речи)")
        self.whisper_model = None
        self.setup_whisper()
        print("✅ whisper готов")

        # TTS
        print("📥 инициализация TTS")
        self.tts = get_tts()
        if self.tts is None:
            print("⚠️ TTS не инициализирован — ассистент будет работать без голоса")
            logger.warning("TTS не инициализирован")
        elif not self.tts.is_ready():
            # Движок создан, но не готов (например, XTTS упал при загрузке).
            # Причину он уже вывел в консоль при своей инициализации.
            print("⚠️ TTS создан, но не готов — ассистент будет работать без голоса")
            logger.warning("TTS создан, но не готов")

        print("\n🎤 юрий готов к работе")

    # ---------- whisper ----------

    def setup_whisper(self):
        """Загружаем Whisper один раз при старте."""
        try:
            self.whisper_model = WhisperModel(
                WHISPER_SETTINGS.get('model_size', 'small'),
                device=WHISPER_SETTINGS.get('device', 'cpu'),
                compute_type=WHISPER_SETTINGS.get('compute_type', 'int8')
            )
            logger.info("whisper модель загружена")
        except Exception as e:
            logger.error(f"ошибка загрузки whisper: {e}")
            print(f"❌ ошибка загрузки whisper: {e}")

    # ---------- запись ----------

    def listen(self,
               sample_rate: Optional[int] = None,
               silence_threshold: Optional[float] = None,
               silence_duration: Optional[float] = None,
               max_duration: Optional[float] = None) -> Optional[np.ndarray]:
        """Пишем с микрофона до наступления тишины."""
        sample_rate = sample_rate or AUDIO_SETTINGS.get('sample_rate', 16000)
        silence_threshold = silence_threshold or AUDIO_SETTINGS.get('silence_threshold', 0.02)
        silence_duration = silence_duration or AUDIO_SETTINGS.get('silence_duration', 2.0)
        max_duration = max_duration or AUDIO_SETTINGS.get('max_duration', 15)

        print(f"\n🎤 слушаю, говорите (остановка после {silence_duration} сек тишины)")

        try:
            audio_chunks = []
            silence_start = None
            is_speaking = False
            start_time = time.time()

            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32') as stream:
                while True:
                    chunk, _ = stream.read(int(sample_rate * 0.1))
                    audio_chunks.append(chunk)

                    rms = np.sqrt(np.mean(chunk ** 2))

                    if rms > silence_threshold:
                        if not is_speaking:
                            print("🔴 говорение началось")
                            is_speaking = True
                        silence_start = None
                    else:
                        if is_speaking:
                            if silence_start is None:
                                silence_start = time.time()
                                print(f"⏸️ тишина (ожидание {silence_duration} сек)")
                            elif time.time() - silence_start >= silence_duration:
                                print("✅ тишина обнаружена, завершаю запись")
                                break

                    if time.time() - start_time > max_duration:
                        print(f"⚠️ достигнуто максимальное время записи ({max_duration} сек)")
                        break

            if audio_chunks:
                recording = np.concatenate(audio_chunks)

                max_level = np.abs(recording).max()
                print(f"📊 максимальный уровень: {max_level:.4f}")
                print(f"📊 длительность записи: {len(recording) / sample_rate:.2f} сек")

                if max_level < 0.001:
                    print("❌ слишком тихо, микрофон не работает")
                    return None

                return recording.flatten()
            else:
                print("❌ нет аудиоданных")
                return None

        except Exception as e:
            print(f"❌ ошибка записи: {e}")
            logger.error(f"ошибка записи аудио: {e}")
            return None

    # ---------- распознавание ----------

    def recognize_speech(self, audio: np.ndarray) -> Optional[str]:
        """Распознаём аудио через Whisper."""
        print("\n🔍 распознаю")

        if self.whisper_model is None:
            print("❌ Whisper не загружен")
            return None

        try:
            segments, info = self.whisper_model.transcribe(
                audio,
                language=WHISPER_SETTINGS.get('language', 'ru'),
                beam_size=WHISPER_SETTINGS.get('beam_size', 5),
                vad_filter=WHISPER_SETTINGS.get('vad_filter', True),
                vad_parameters=WHISPER_SETTINGS.get('vad_parameters', dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                ))
            )

            print(f"📊 язык: {info.language} (вероятность: {info.language_probability:.2%})")

            text_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    print(f"  [{segment.start:.2f}s - {segment.end:.2f}s] {text}")
                    text_parts.append(text)

            full_text = " ".join(text_parts)

            if full_text:
                print(f"\n✅ распознано: {full_text}")
                return full_text
            else:
                print("\n❌ ничего не распознано")
                return None

        except Exception as e:
            print(f"❌ ошибка распознавания: {e}")
            logger.error(f"ошибка распознавания речи: {e}")
            return None

    # ---------- синтез ----------

    def synthesize_speech(self, text: str):
        """
        Озвучиваем текст. Если TTS не готов — молча пропускаем.
        Причина уже была выведена при инициализации движка.
        """
        if not text:
            return

        if self.tts is None:
            return

        if not self.tts.is_ready():
            # Тихо. Пользователь уже видел причину при старте ассистента.
            return

        print(f"\n🗣️ озвучиваю: {text}")
        success = self.tts.speak(text)
        if success:
            print("✅ озвучка завершена")
        else:
            print("❌ не удалось озвучить")

    # ---------- обработка команды ----------

    def process_command(self, command: str) -> Optional[str]:
        """Проверяем wake-word, чистим команду, отдаём в command_processor."""
        try:
            if not contains_wake_word(command):
                return None

            clean_command = extract_command_without_wake_word(command)

            if not clean_command:
                import random
                from config import RESPONSES
                return random.choice(RESPONSES.get('wake_word_only', ['слушаю']))

            response = command_processor.process_command(clean_command, command)
            return response

        except Exception as e:
            logger.error(f"ошибка обработки команды: {e}")
            return "произошла ошибка при обработке команды"

    # ---------- основной цикл ----------

    def run_once(self):
        """Один цикл: послушать → распознать → выполнить → озвучить."""
        audio = self.listen()
        if audio is None:
            print("попробуйте еще раз")
            return

        recognized_text = self.recognize_speech(audio)

        if recognized_text:
            if not contains_wake_word(recognized_text):
                print(f"⏭️ команда без обращения пропущена: {recognized_text}")
                return

            response_text = self.process_command(recognized_text)
            if response_text:
                self.synthesize_speech(response_text)
            else:
                print("❌ команда не обработана")

    def run_loop(self):
        """Бесконечный цикл прослушивания."""
        print("\n" + "=" * 50)
        print("🎤 юрий: слушаю и выполняю команды")
        print("нажмите ctrl+c для выхода")
        print("=" * 50)

        try:
            while True:
                self.run_once()
                print("\n" + "-" * 30)
        except KeyboardInterrupt:
            print("\n\n👋 до свидания")
        finally:
            if self.tts is not None:
                try:
                    self.tts.stop()
                except Exception as e:
                    logger.debug(f"ошибка остановки TTS: {e}")

    def listen_and_process(self) -> Tuple[Optional[str], Optional[str]]:
        """Слушаем и обрабатываем одну команду. Для внешних вызовов."""
        audio = self.listen()
        if audio is None:
            return None, None

        recognized_text = self.recognize_speech(audio)
        if not recognized_text:
            return None, None

        if not contains_wake_word(recognized_text):
            return recognized_text, None

        response = self.process_command(recognized_text)
        return recognized_text, response


# ---------- ленивый синглтон ----------

_assistant_instance: Optional[VoiceAssistant] = None


def get_voice_assistant() -> VoiceAssistant:
    """
    Возвращает глобальный экземпляр VoiceAssistant, создавая его
    при первом обращении. Раньше объект создавался прямо при импорте
    модуля — это приводило к двойной инициализации Whisper и TTS.
    """
    global _assistant_instance
    if _assistant_instance is None:
        _assistant_instance = VoiceAssistant()
    return _assistant_instance


# ---------- совместимость со старым API ----------

def listen(sample_rate=None, silence_threshold=None, silence_duration=None, max_duration=None):
    return get_voice_assistant().listen(sample_rate, silence_threshold, silence_duration, max_duration)


def recognize_speech(audio):
    return get_voice_assistant().recognize_speech(audio)


def synthesize_speech(text):
    return get_voice_assistant().synthesize_speech(text)