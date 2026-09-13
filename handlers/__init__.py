"""
Обработчики команд
"""

from handlers.base_handler import BaseHandler
from handlers.program_handler import ProgramHandler
from handlers.audio_handler import AudioHandler
from handlers.display_handler import DisplayHandler
from handlers.window_handler import WindowHandler
from handlers.browser_handler import BrowserHandler
from handlers.system_handler import SystemHandler

__all__ = [
    'BaseHandler',
    'ProgramHandler',
    'AudioHandler',
    'DisplayHandler',
    'WindowHandler',
    'BrowserHandler',
    'SystemHandler'
]