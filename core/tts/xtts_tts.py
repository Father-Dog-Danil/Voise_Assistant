"""
XTTS v2 — нейросетевой TTS с клонированием голоса.

Модель тяжёлая, стартует долго (30-60 сек), ест VRAM. Держать её
в основном процессе плохо — она будет конкурировать с Whisper
и другой нейронкой за GPU. Поэтому выносим в отдельный процесс
(воркер), общаемся через stdin/stdout построчно.

Загрузка модели происходит сразу при создании объекта — ждём её
столько, сколько потребуется. Если что-то не так (нет донора,
нет библиотеки, воркер упал) — пишем конкретную причину в консоль,
флаг _ready остаётся False, speak() молча возвращает False.
Никакой подмены движка.
"""

import os
import sys
import logging
import tempfile
import subprocess
from typing import Optional

import numpy as np
import soundfile as sf
import sounddevice as sd

from core.tts.base_tts import BaseTTS

logger = logging.getLogger(__name__)

# Код воркера пишется во временный файл при инициализации.
# Держать отдельный .py в проекте не хочется — воркер тесно связан
# с этим классом и меняется вместе с ним.
_WORKER_CODE = '''
import sys
import os
import tempfile
import torch
import soundfile as sf

try:
    from TTS.api import TTS
except Exception as e:
    print(f"IMPORT_ERROR:{e}", flush=True)
    sys.exit(2)

speaker_wav = sys.argv[1]
device_str = sys.argv[2]
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

if device_str == "auto":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
else:
    device = torch.device(device_str)

print(f"DEVICE:{device}", flush=True)

try:
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
except Exception as e:
    print(f"MODEL_ERROR:{e}", flush=True)
    sys.exit(3)

print("READY", flush=True)

for line in sys.stdin:
    text = line.strip()
    if not text:
        continue
    if text == "EXIT":
        break
    try:
        audio = tts.tts(text=text, speaker_wav=speaker_wav, language="ru", speed=speed)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, audio, 24000)
        print(f"DONE:{tmp_path}", flush=True)
    except Exception as e:
        print(f"ERROR:{e}", flush=True)
'''


class XttsTTS(BaseTTS):
    """
    Обёртка над XTTS-воркером.

    В __init__ сразу поднимаем воркер и ждём READY. Если не получилось —
    пишем конкретную причину в консоль и в лог, _ready остаётся False,
    speak() возвращает False. Ассистент работает без голоса.
    """

    def __init__(self, settings: dict, base_dir: str):
        super().__init__(settings)

        self.base_dir = base_dir
        self.sample_rate = int(self.settings.get('sample_rate', 24000))
        self.speed = float(self.settings.get('speed', 1.3))

        # Путь к временному файлу воркера
        self._worker_path = os.path.join(
            tempfile.gettempdir(), 'yuriy_xtts_worker.py'
        )

        # Путь к голосу-донору
        self.speaker_wav: Optional[str] = None

        # Процесс-воркер
        self._process: Optional[subprocess.Popen] = None

        # Причина, по которой движок не готов (для логов и консоли)
        self.error_message: Optional[str] = None

        # --- загрузка ---
        # Порядок важен: сначала проверяем внешние условия, потом
        # пишем воркер, потом его запускаем.
        if not self._check_dependencies():
            return
        if not self._resolve_speaker_wav():
            return
        if not self._prepare_worker_file():
            return
        self._start_worker()

    # ---------- проверки ----------

    def _check_dependencies(self) -> bool:
        """Проверяем, что установлена библиотека TTS (Coqui)."""
        try:
            import TTS  # noqa: F401
            return True
        except ImportError:
            msg = ("XTTS: библиотека TTS (Coqui) не установлена. "
                   "Установите: pip install TTS")
            self.error_message = msg
            print(f"❌ {msg}")
            logger.error(msg)
            return False

    def _resolve_speaker_wav(self) -> bool:
        """Превращаем относительный путь в абсолютный и проверяем."""
        raw = self.settings.get('speaker_wav', '')

        if not raw:
            msg = "XTTS: в конфиге не указан speaker_wav (файл-донор голоса)"
            self.error_message = msg
            print(f"❌ {msg}")
            logger.error(msg)
            return False

        full = raw if os.path.isabs(raw) else os.path.join(self.base_dir, raw)

        if not os.path.exists(full):
            msg = f"XTTS: файл-донор голоса не найден: {full}"
            self.error_message = msg
            print(f"❌ {msg}")
            logger.error(msg)
            return False

        self.speaker_wav = full
        return True

    def _prepare_worker_file(self) -> bool:
        """Пишем код воркера в temp-файл."""
        try:
            with open(self._worker_path, 'w', encoding='utf-8') as f:
                f.write(_WORKER_CODE)
            logger.debug(f"воркер XTTS записан: {self._worker_path}")
            return True
        except Exception as e:
            msg = f"XTTS: не удалось записать воркер в {self._worker_path}: {e}"
            self.error_message = msg
            print(f"❌ {msg}")
            logger.error(msg)
            return False

    def _start_worker(self):
        """Запускаем воркер и ждём READY. Ждём сколько угодно."""
        print("📥 загрузка XTTS v2 (может занять 30-60 сек)...")

        device = self.settings.get('device', 'auto')

        try:
            self._process = subprocess.Popen(
                [sys.executable, self._worker_path,
                 self.speaker_wav, device, str(self.speed)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
            )
        except Exception as e:
            msg = f"XTTS: не удалось запустить воркер: {e}"
            self.error_message = msg
            print(f"❌ {msg}")
            logger.error(msg)
            self._process = None
            return

        # Ждём READY. По пути показываем всё, что печатает воркер.
        while True:
            line = self._process.stdout.readline()
            if not line:
                msg = "XTTS: воркер закрылся, не дождавшись READY"
                self.error_message = msg
                print(f"❌ {msg}")
                logger.error(msg)
                self._process = None
                return

            line = line.strip()
            if not line:
                continue

            if line == 'READY':
                self._ready = True
                print("✅ XTTS готов")
                logger.info("XTTS-воркер готов")
                return

            if line.startswith('IMPORT_ERROR:'):
                msg = f"XTTS: ошибка импорта TTS в воркере: {line[13:]}"
                self.error_message = msg
                print(f"❌ {msg}")
                logger.error(msg)
                self._terminate_worker()
                return

            if line.startswith('MODEL_ERROR:'):
                msg = f"XTTS: ошибка загрузки модели: {line[12:]}"
                self.error_message = msg
                print(f"❌ {msg}")
                logger.error(msg)
                self._terminate_worker()
                return

            # Прочие строки — просто транслируем в лог
            logger.info(f"[xtts-worker] {line}")

    def _terminate_worker(self):
        """Прибить воркер, если он висит."""
        if self._process is None:
            return
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
        except Exception:
            pass
        finally:
            self._process = None
            self._ready = False

    # ---------- публичный интерфейс ----------

    def speak(self, text: str) -> bool:
        """Озвучивает текст. Если движок не готов — молча False."""
        if not text or not text.strip():
            return False

        if not self._ready or self._process is None:
            # Причина уже была выведена при инициализации,
            # повторять её на каждый ответ не надо.
            return False

        try:
            self._process.stdin.write(text + '\n')
            self._process.stdin.flush()

            while True:
                line = self._process.stdout.readline()
                if not line:
                    msg = "XTTS: воркер неожиданно закрылся во время синтеза"
                    print(f"❌ {msg}")
                    logger.error(msg)
                    self.error_message = msg
                    self._ready = False
                    self._process = None
                    return False

                line = line.strip()
                if not line:
                    continue

                if line.startswith('DONE:'):
                    return self._play_and_cleanup(line[5:])

                if line.startswith('ERROR:'):
                    print(f"❌ XTTS: ошибка синтеза: {line[6:]}")
                    logger.error(f"XTTS-воркер вернул ошибку: {line[6:]}")
                    return False

                logger.debug(f"[xtts-worker] {line}")

        except Exception as e:
            msg = f"XTTS: ошибка общения с воркером: {e}"
            print(f"❌ {msg}")
            logger.error(msg)
            self.error_message = msg
            self._ready = False
            return False

    def stop(self):
        """Останавливаем воркер."""
        if self._process is None:
            return
        try:
            if self._process.poll() is None:
                try:
                    self._process.stdin.write('EXIT\n')
                    self._process.stdin.flush()
                except Exception:
                    pass
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
        except Exception as e:
            logger.debug(f"ошибка остановки XTTS-воркера: {e}")
        finally:
            self._process = None
            self._ready = False

    # ---------- вспомогательное ----------

    def _play_and_cleanup(self, wav_path: str) -> bool:
        """Читаем WAV, удаляем файл, играем."""
        if not os.path.exists(wav_path):
            logger.error(f"XTTS вернул путь, но файла нет: {wav_path}")
            return False

        try:
            audio, sr = sf.read(wav_path)
        except Exception as e:
            logger.error(f"не удалось прочитать WAV от XTTS: {e}")
            self._try_remove(wav_path)
            return False

        self._try_remove(wav_path)

        try:
            sd.play(audio, sr)
            sd.wait()
            return True
        except Exception as e:
            logger.error(f"ошибка воспроизведения XTTS: {e}")
            return False

    @staticmethod
    def _try_remove(path: str):
        try:
            os.remove(path)
        except Exception:
            pass

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass