"""
Голосовой ассистент Юрий.
Точка входа в приложение.
"""

import os
import sys
import logging

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    LOG_FILES_DIR,
    JSONS_FILES_DIR,
    MODELS_DIR,
    TTS_SETTINGS,
    pyautogui_settings,
)
from core.voice_assistant import VoiceAssistant
from core.command_processor import command_processor
from core.tts import get_tts

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_FILES_DIR, 'yuriy_assistant.log'),
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_environment():
    """Настройка окружения перед запуском."""
    import pyautogui
    pyautogui.FAILSAFE = pyautogui_settings.get('failsafe', True)
    pyautogui.PAUSE = pyautogui_settings.get('pause', 0.1)

    os.makedirs(LOG_FILES_DIR, exist_ok=True)
    os.makedirs(JSONS_FILES_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    logger.info("окружение настроено")


def print_startup_info():
    """Информация при запуске."""
    engine = TTS_SETTINGS.get('engine', 'piper')

    print("🚀 запуск голосового ассистента")
    print("🎤 используется whisper для распознавания речи")
    if engine == 'xtts':
        print("🗣️ используется XTTS v2 для синтеза речи (нейросетевой голос)")
    else:
        print("🗣️ используется piper tts для синтеза речи")
    print()
    print("📁 файлы будут сохраняться в:")
    print(f"   • логи: {LOG_FILES_DIR}/")
    print(f"   • json: {JSONS_FILES_DIR}/")
    print()
    print("✅ функциональность:")
    print("• голосовое управление компьютером")
    print("• динамическая база данных программ из json")
    print("• команда 'обнови пути' для сканирования программ")
    print("• автоматическое распознавание установленных приложений")
    print("• отложенное выполнение команд в фоновом режиме")
    print("• отмена закрытия программ")
    print("• правильное управление яркостью с запоминанием значений")
    print()
    print("🎯 ассистент активируется только после обращения:")
    print("   • 'юра', 'юрий', 'юр' и другие варианты")
    print("   • например: 'юра, открой хром'")
    print()
    print("💡 скажи 'помощь' для полного списка команд")
    print()


def run_voice_mode():
    """
    Голосовой режим.

    VoiceAssistant создаётся здесь, а не на уровне модуля — так
    управляем временем жизни TTS и вовремя освобождаем ресурсы.
    """
    assistant = VoiceAssistant()
    try:
        assistant.run_loop()
    finally:
        try:
            tts = get_tts()
            if tts is not None:
                tts.stop()
        except Exception as e:
            logger.debug(f"ошибка остановки TTS: {e}")


def run_cli_mode():
    """Режим командной строки."""
    print("\n📝 режим командной строки")
    print("введите команду или 'выход' для завершения")
    print("=" * 50)

    while True:
        try:
            command = input("\n> ").strip()

            if command.lower() in ['выход', 'exit', 'quit']:
                print("👋 до свидания")
                break

            if command:
                response = command_processor.process_command(command)
                print(f"🤖 {response}")

        except KeyboardInterrupt:
            print("\n\n👋 до свидания")
            break
        except Exception as e:
            logger.error(f"ошибка в CLI режиме: {e}")
            print(f"❌ ошибка: {e}")


def run_flask_mode(host: str = '127.0.0.1', port: int = 5000):
    """Flask API режим."""
    from flask import Flask, request, jsonify

    app = Flask(__name__)

    @app.route('/', methods=['POST'])
    def handle_request():
        try:
            data = request.get_json()
            response_data = command_processor.process_with_context(data)
            return jsonify(response_data)
        except Exception as e:
            logger.error(f"ошибка обработки запроса: {e}")
            return jsonify({
                "version": "1.0",
                "session": {},
                "response": {
                    "text": "произошла ошибка",
                    "end_session": False
                }
            })

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "OK", "message": "Server is running"})

    print(f"🌐 Flask сервер запущен на http://{host}:{port}")
    app.run(host=host, port=port)


def main():
    """Точка входа."""
    try:
        setup_environment()
        print_startup_info()

        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()

            if mode in ['--voice', '-v']:
                run_voice_mode()
            elif mode in ['--cli', '-c']:
                run_cli_mode()
            elif mode in ['--flask', '-f']:
                host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
                port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
                run_flask_mode(host, port)
            elif mode in ['--help', '-h']:
                print_usage()
            else:
                print(f"❌ неизвестный режим: {mode}")
                print_usage()
        else:
            run_voice_mode()

    except KeyboardInterrupt:
        print("\n\n👋 до свидания")
    except Exception as e:
        logger.error(f"критическая ошибка: {e}")
        print(f"❌ критическая ошибка: {e}")
    finally:
        # Страховка на верхнем уровне: если что-то упало,
        # всё равно пробуем остановить TTS-воркер.
        try:
            tts = get_tts()
            if tts is not None:
                tts.stop()
        except Exception:
            pass


def print_usage():
    """Инструкция по использованию."""
    print("""
📋 Использование:
    python main.py [режим] [параметры]

Режимы:
    --voice, -v     Голосовой режим (по умолчанию)
    --cli, -c       Режим командной строки
    --flask, -f     Flask API режим [host] [port]
    --help, -h      Показать эту справку

Примеры:
    python main.py                    # Голосовой режим
    python main.py --cli              # CLI режим
    python main.py --flask 127.0.0.1 5000  # Flask API
    """)


if __name__ == '__main__':
    main()