"""
Piper TTS — лёгкий движок озвучки на CPU.

Работает через CLI piper.exe: пишем текст в stdin, читаем сырые
PCM-байты из stdout, играем через sounddevice. Никаких python-обёрток,
потому что они тянут лишние зависимости и ведут себя по-разному
в зависимости от версии piper.

Движок рассчитан на слабые устройства: голос роботизированный,
но работает везде, где есть Python и piper.exe.
"""

import os
import shutil
import subprocess
import logging
from typing import Optional

import numpy as np
import sounddevice as sd

from core.tts.base_tts import BaseTTS

logger = logging.getLogger(__name__)


class PiperTTS(BaseTTS):
    """
    Обёртка над piper.exe.

    Настройки (из config.TTS_SETTINGS['piper']):
      - model_name: имя .onnx-модели в папке models/
      - config_name: имя .onnx.json-конфига в папке models/
      - sample_rate: частота дискретизации (обычно 22050)
      - exe_search_paths: где искать piper.exe относительно BASE_DIR
    """

    def __init__(self, settings: dict, models_dir: str, base_dir: str):
        super().__init__(settings)

        self.models_dir = models_dir
        self.base_dir = base_dir

        self.piper_exe: Optional[str] = None
        self.model_path: Optional[str] = None
        self.config_path: Optional[str] = None
        self.sample_rate: int = int(self.settings.get('sample_rate', 22050))

        self._setup()
        self._ready = self._check_ready()

    # ---------- инициализация ----------

    def _setup(self):
        """Ищет piper.exe и файлы модели."""
        self._find_piper_exe()
        self._resolve_model_paths()

    def _find_piper_exe(self):
        """Ищем piper.exe: сначала в указанных папках, потом в PATH."""
        for rel_path in self.settings.get('exe_search_paths', []):
            full_path = os.path.join(self.base_dir, rel_path)
            if os.path.exists(full_path):
                self.piper_exe = full_path
                logger.info(f"piper.exe найден: {full_path}")
                return

        # Последняя попытка — PATH
        found = shutil.which('piper')
        if found:
            self.piper_exe = found
            logger.info(f"piper.exe найден в PATH: {found}")
        else:
            logger.error("piper.exe не найден ни в папках проекта, ни в PATH")

    def _resolve_model_paths(self):
        """Собираем полные пути к .onnx и .onnx.json."""
        model_name = self.settings.get('model_name')
        config_name = self.settings.get('config_name')

        if model_name:
            self.model_path = os.path.join(self.models_dir, model_name)
        if config_name:
            self.config_path = os.path.join(self.models_dir, config_name)

    def _check_ready(self) -> bool:
        """Проверяем, что всё на месте, иначе смысла работать нет."""
        if not self.piper_exe:
            return False
        if not self.model_path or not os.path.exists(self.model_path):
            logger.error(f"модель Piper не найдена: {self.model_path}")
            return False
        return True

    # ---------- публичный интерфейс ----------

    def speak(self, text: str) -> bool:
        """
        Синтезирует и проигрывает текст. Блокирующий вызов.

        Логика простая: пишем текст в stdin piper.exe, читаем
        сырые PCM-байты из stdout, конвертируем в numpy int16
        и отдаём в sounddevice.
        """
        if not text or not text.strip():
            return False

        if not self._ready:
            logger.error("PiperTTS не готов (нет exe или модели)")
            return False

        try:
            cmd = [
                self.piper_exe,
                '--model', self.model_path,
                '--output_raw',
            ]

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            audio_bytes, _ = process.communicate(input=text.encode('utf-8'))

            if not audio_bytes:
                logger.error("piper не вернул аудиоданные")
                return False

            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

            sd.play(audio_data, self.sample_rate)
            sd.wait()

            return True

        except Exception as e:
            logger.error(f"ошибка синтеза Piper: {e}")
            return False

    def stop(self):
        """
        У Piper нет отдельного процесса, который надо убивать —
        subprocess завершается сам после communicate().
        Останавливаем звук на случай, если он ещё играет.
        """
        try:
            sd.stop()
        except Exception as e:
            logger.debug(f"sd.stop() вернул ошибку: {e}")

    # ---------- удобные обёртки ----------

    def preload(self):
        """
        Для Piper прогрев не нужен — он стартует мгновенно.
        Метод оставлен для совместимости с интерфейсом BaseTTS.
        """
        pass