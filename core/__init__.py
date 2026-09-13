"""
Ядро голосового ассистента.

Публичный интерфейс намеренно узкий: VoiceAssistant и CommandProcessor.
Экземпляр ассистента через импорт не создаётся — только класс.
Хочешь готовый объект — дергай core.voice_assistant.get_voice_assistant().
"""

from core.voice_assistant import VoiceAssistant, get_voice_assistant
from core.command_processor import CommandProcessor

__all__ = ['VoiceAssistant', 'get_voice_assistant', 'CommandProcessor']