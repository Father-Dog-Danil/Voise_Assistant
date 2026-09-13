"""
Сканер программ Windows
Находит установленные программы и создает базу данных для голосового ассистента
"""

import winreg
import os
import re
import json
import sys
import subprocess
from itertools import product
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging
from collections import defaultdict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class ProgramScanner:
    """Класс для сканирования и управления программами Windows"""

    def __init__(self):
        # Используем путь относительно текущего файла для новой структуры
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / "data" / "jsons"
        self.output_file = self.output_dir / "programs_database.json"

        # Создаем директорию если её нет
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Ключи реестра для сканирования
        self.registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]

        self.registry_hives = [
            (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
            (winreg.HKEY_CURRENT_USER, "HKCU"),
        ]

        # Паттерны для определения системных компонентов
        self.system_patterns = [
            # Системные компоненты Windows
            r'.*windows.*(?:update|component|service|driver|runtime|framework).*',
            r'.*microsoft.*(?:\.net|visual c\+\+|sdk|build tools|targeting pack|apphost|toolset|templates).*',
            r'.*microsoft.*(?:windows|office).*(?:component|service|update|language).*',
            r'.*(?:driver|hal|ppm|gpio|psp|smbus|promontory).*',
            r'.*(?:telemetry|container|watchdog|bootstrap).*',
            r'.*click-to-run.*',
            r'.*redistributable.*',
            r'.*service pack.*',
            r'.*hotfix.*',
            r'.*security update.*',
            r'.*language pack.*',
            r'.*prerequisite.*',

            # Встроенные утилиты Windows
            r'.*(?:task manager|registry editor|command prompt|powershell|control panel).*',
            r'.*(?:disk cleanup|resource monitor|system information|system configuration).*',
            r'.*(?:character map|magnifier|narrator|on-screen keyboard).*',
            r'.*(?:odbc|iscsi|memory diagnostics|recovery).*',
            r'.*(?:administrative tools|windows media player legacy|windows defender).*',
            r'.*(?:livecaptions|voiceaccess|dfrgui).*',

            # Средства разработки которые не нужно запускать
            r'.*\.net.*(?:sdk|runtime|host|targeting|apphost|toolset|templates|workload).*',
            r'.*build tools.*',
            r'.*visual studio.*(?:installer|setup|wmi|provider).*',

            # Установщики и деинсталляторы
            r'.*(?:uninstall|deinstall|удалить|деинсталл|установить).*',
            r'.*(?:installer|setup|configuration).*',

            # Компоненты производителей железа
            r'.*nvidia.*(?:messagebus|backend|frameview|install application|nvdlisr|virtual audio|shadowplay|driver).*',
            r'.*amd.*(?:ryzen master sdk|software|driver|gpio|psp|smbus).*',
            r'.*realtek.*(?:audio|driver|ethernet|wireless).*',
            r'.*intel.*(?:driver|management|wireless|graphics).*',

            # Сервисы и фоновые процессы
            r'.*maintenance service.*',
            r'.*redeem launcher.*',
            r'.*webview.*runtime.*',
            r'.*edge webview.*',
            r'.*dropbox redeem.*',

            # Служебные программы
            r'.*ota dependencies.*',
            r'.*market research.*',
            r'.*file tracker.*',
            r'.*user container.*',
            r'.*session container.*',
            r'.*localsystem container.*',

            # Античиты и защита
            r'.*vanguard.*',
            r'.*anticheat.*',
            r'.*anti-cheat.*',
            r'.*easy anti.*',
            r'.*battleye.*',
        ]

        # Паттерны для определения мусорных путей
        self.trash_path_patterns = [
            r'.*uninstall.*\.exe$',
            r'.*uninst.*\.exe$',
            r'.*setup.*\.exe$',
            r'.*installer.*\.exe$',
            r'.*dotnetfx.*\.exe$',
            r'.*agentactivationruntimestarter\.exe$',
            r'.*clicktorun.*\.exe$',
            r'.*cache.*\.exe$',
            r'.*helper.*\.exe$',
            r'.*crash.*\.exe$',
            r'.*error.*\.exe$',
            r'.*telemetry.*\.exe$',
            r'.*log-uploader\.exe$',
            r'.*appvdllsurrogate\.exe$',
            r'.*rundll32\.exe$',
            r'.*maintenanceservice\.exe$',
            r'.*nvfvsdksvc.*\.exe$',
        ]

        # Паттерны для служебных программ Microsoft Office
        self.office_utility_patterns = [
            r'.*телеметри.*',
            r'.*языковые параметр.*',
            r'.*spreadsheet compare.*',
            r'.*clicktorun.*',
            r'.*appvlp.*',
            r'.*msoev.*',
            r'.*setlang.*',
        ]

        # Категории программ с ключевыми словами
        self.categories_config = {
            '🎮 Игры': {
                'keywords': [
                    'game', 'игра', 'steam', 'impact', 'knight', 'terraria',
                    'isaac', 'counter-strike', 'osu!', 'dead cells', 'battlegrounds',
                    'ведьмак', 'starve', 'oxygen', 'biped', 'silksong', 'tmodloader',
                    'tlauncher', 'hoyoplay', 'epic games', 'battle.net', 'origin',
                    'gog', 'ubisoft', 'riot client', 'blizzard', 'valorant', 'minecraft',
                    'terraria', 'stardew', 'factorio', 'rimworld', 'cs:go',
                    'dota', 'league of legends', 'world of warcraft', 'overwatch',
                    'prism launcher', 'gog galaxy'
                ],
                'exclude': ['vanguard', 'anticheat', 'anti-cheat']
            },
            '🌐 Браузеры и мессенджеры': {
                'keywords': [
                    'browser', 'браузер', 'chrome', 'firefox', 'edge', 'yandex',
                    'telegram', 'телеграм', 'discord', 'whatsapp', 'viber', 'skype',
                    'zoom', 'teamviewer', 'anydesk', 'messenger', 'мессенджер',
                    'slack', 'signal', 'threema', 'wechat', 'line', 'kakaotalk',
                    'opera', 'brave', 'vivaldi', 'tor browser'
                ],
                'exclude': ['webview', 'runtime', 'private']
            },
            '💻 Рабочие программы': {
                'keywords': [
                    'office', 'word', 'excel', 'powerpoint', 'onenote', 'outlook',
                    'pycharm', 'visual studio code', 'notepad++', 'pdf', 'editor',
                    'sublime', 'atom', 'eclipse', 'intellij',
                    'photoshop', 'illustrator', 'indesign', 'autocad', 'blender',
                    'maya', '3ds max', 'cinema 4d', 'unity', 'unreal',
                    'vs code', 'vscode', 'android studio', 'xcode',
                    'paint.net', 'gimp', 'inkscape', 'scribus'
                ],
                'exclude': ['installer', 'setup', 'build tools', 'телеметри', 'языковые']
            },
            '🛠️ Утилиты': {
                'keywords': [
                    'cpu-z', 'crystaldisk', 'afterburner', 'rivatuner', 'furmark',
                    'wiztree', 'equalizer', 'qbittorrent', 'wallpaper', 'razer',
                    'flydigi', 'msi center', 'mysticlight', 'nvidia broadcast', 'peak',
                    'velocityx', 'cleaner', 'optimizer',
                    'monitor', 'benchmark', 'overclock', 'rgb', 'lighting',
                    'fan control', 'temperature', 'diagnostic', 'aida64',
                    'sharex', 'everything', 'lockhunter', 'windhawk',
                    '7-zip', 'winrar', 'winzip', 'peazip',
                    'daemon tools', 'virtual clone', 'alcohol',
                    'nomachine', 'parsec',
                    'obs', 'streamlabs', 'xsplit',
                    'voicemeeter', 'equalizer apo', 'peace',
                    'evga precision', 'asus gpu tweak',
                    'geany', 'git', 'python', 'free pascal',
                    'bloody workshop', 'makutweaker', 'incy',
                    'aitppt', 'capcut'
                ]
            },
            '🎵 Мультимедиа': {
                'keywords': [
                    'vlc', 'media player', 'spotify', 'itunes', 'winamp',
                    'audacity', 'obs', 'streamlabs', 'premiere', 'after effects',
                    'vegas', 'audition', 'fl studio', 'ableton', 'reaper',
                    'music', 'video', 'audio', 'player', 'media', 'multimedia',
                    'handbrake', 'davinci', 'kdenlive', 'shotcut',
                    'mpc-hc', 'potplayer', 'kmplayer'
                ]
            },
        }

        # Словарь транслитерации
        self.translit_dict = {
            'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г',
            'h': 'х', 'i': 'и', 'j': 'дж', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н',
            'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
            'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'и', 'z': 'з',
            'ch': 'ч', 'sh': 'ш', 'th': 'з', 'ph': 'ф', 'wh': 'в',
            'ya': 'я', 'ye': 'е', 'yo': 'ё', 'yu': 'ю', 'zh': 'ж', 'kh': 'х',
            'ts': 'ц', 'sch': 'щ', 'shch': 'щ'
        }

        # Популярные программы с произношением
        self.popular_programs = {
            'steam': {'ru': ['стим', 'стем'], 'category': '🎮 Игры'},
            'counter strike': {'ru': ['каунтер страйк', 'контер страйк', 'кс'], 'category': '🎮 Игры'},
            'dead cells': {'ru': ['дэд селлс', 'дед селлс'], 'category': '🎮 Игры'},
            'hollow knight': {'ru': ['холлоу найт', 'холоу найт'], 'category': '🎮 Игры'},
            'genshin impact': {'ru': ['геншин импакт', 'гэншин импакт'], 'category': '🎮 Игры'},
            'dont starve together': {'ru': ['донт старв тугезер', 'дон старв тугезер'], 'category': '🎮 Игры'},
            'chrome': {'ru': ['хром', 'кром', 'гугл хром'], 'category': '🌐 Браузеры и мессенджеры'},
            'firefox': {'ru': ['фаерфокс', 'файрфокс', 'мозила'], 'category': '🌐 Браузеры и мессенджеры'},
            'edge': {'ru': ['эдж', 'едж', 'майкрософт эдж'], 'category': '🌐 Браузеры и мессенджеры'},
            'yandex browser': {'ru': ['яндекс браузер', 'яндекс'], 'category': '🌐 Браузеры и мессенджеры'},
            'telegram': {'ru': ['телеграм', 'телега', 'тг'], 'category': '🌐 Браузеры и мессенджеры'},
            'discord': {'ru': ['дискорд', 'дискач', 'дс'], 'category': '🌐 Браузеры и мессенджеры'},
            'whatsapp': {'ru': ['ватсап', 'вотсап', 'вацап'], 'category': '🌐 Браузеры и мессенджеры'},
            'pycharm': {'ru': ['пайчарм', 'пичарм'], 'category': '💻 Рабочие программы'},
            'visual studio code': {'ru': ['вижуал студио код', 'вс код'], 'category': '💻 Рабочие программы'},
            'notepad++': {'ru': ['нотепад плюс плюс', 'нотпаd'], 'category': '💻 Рабочие программы'},
            'office': {'ru': ['офис', 'майкрософт офис'], 'category': '💻 Рабочие программы'},
            'wallpaper engine': {'ru': ['волпейпер енджин', 'уоллпейпер энджин', 'обои'], 'category': '🛠️ Утилиты'},
            'nvidia broadcast': {'ru': ['энвидиа бродкаст', 'нвидиа бродкаст'], 'category': '🛠️ Утилиты'},
            'msi afterburner': {'ru': ['эмэсай афтербернер', 'мси афтербернер'], 'category': '🛠️ Утилиты'},
            'qbittorrent': {'ru': ['кубитторент', 'кьюбитторент', 'торрент'], 'category': '🛠️ Утилиты'},
            'vlc': {'ru': ['влс', 'виэлси', 'влц'], 'category': '🎵 Мультимедиа'},
            'spotify': {'ru': ['спотифай', 'спотифай'], 'category': '🎵 Мультимедиа'},
            'valorant': {'ru': ['валорант', 'валорант'], 'category': '🎮 Игры'},
            'riot client': {'ru': ['райот клиент', 'риот клиент'], 'category': '🎮 Игры'},
        }

    def is_system_component(self, name: str) -> bool:
        """Проверяет является ли программа системным компонентом"""
        name_lower = name.lower()

        # Проверяем по паттернам
        for pattern in self.system_patterns:
            if re.match(pattern, name_lower, re.IGNORECASE):
                return True

        # Проверяем служебные программы Office
        for pattern in self.office_utility_patterns:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return True

        return False

    def is_trash_path(self, path: str) -> bool:
        """Проверяет является ли путь мусорным"""
        if not path or path.startswith('❓'):
            return True

        path_lower = path.lower()

        for pattern in self.trash_path_patterns:
            if re.search(pattern, path_lower):
                return True

        return False

    def extract_base_name(self, name: str) -> str:
        """Извлекает базовое имя программы без версии и лишних слов"""
        # Убираем версии
        name = re.sub(r'\bv?\d+(\.\d+)*\b', '', name)
        name = re.sub(r'\b(?:version|ver|build)\b', '', name, flags=re.IGNORECASE)

        # Убираем лишние слова
        filler_words = [
            'x64', 'x86', '64-bit', '32-bit', 'amd64', 'ru-ru', 'en-us',
            'for', 'the', 'and', 'with', 'without', 'edition', 'version',
            'desktop', 'application', 'software', 'program', 'tool',
            'skinned', 'reset', 'preferences', 'cache', 'files',
            'private', 'browsing', 'manager', 'file'
        ]
        for word in filler_words:
            name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)

        # Очищаем от лишних пробелов и запятых
        name = name.replace(',', ' ')
        name = ' '.join(name.split())

        return name.strip()

    def normalize_program_name(self, name: str) -> str:
        """Нормализует название программы для сравнения"""
        # Приводим к нижнему регистру
        name = name.lower()

        # Убираем версии
        name = re.sub(r'\bv?\d+(\.\d+)*\b', '', name)

        # Убираем специальные символы
        name = re.sub(r'[^\w\s]', '', name)

        # Убираем лишние пробелы
        name = ' '.join(name.split())

        return name.strip()

    def get_program_category(self, name: str) -> str:
        """Определяет категорию программы на основе её названия"""
        name_lower = name.lower()

        # Проверяем популярные программы
        for prog_name, prog_data in self.popular_programs.items():
            if prog_name in name_lower:
                # Проверяем исключения
                if 'exclude' in prog_data:
                    if any(excl in name_lower for excl in prog_data['exclude']):
                        continue
                return prog_data['category']

        # Проверяем по ключевым словам
        for category, config in self.categories_config.items():
            # Проверяем исключения
            if 'exclude' in config:
                if any(excl in name_lower for excl in config['exclude']):
                    continue

            # Проверяем ключевые слова
            if any(keyword in name_lower for keyword in config['keywords']):
                return category

        return '🛠️ Утилиты'

    def find_exe_path(self, subkey, display_name: str) -> str:
        """Находит путь к исполняемому файлу программы"""
        # Пробуем получить из DisplayIcon
        try:
            display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
            if display_icon and '.exe' in display_icon.lower():
                exe_path = display_icon.replace('"', '').split(',')[0]
                if os.path.exists(exe_path) and not self.is_trash_path(exe_path):
                    return exe_path
        except (FileNotFoundError, OSError):
            pass

        # Пробуем получить из InstallLocation
        try:
            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
            if install_location and os.path.exists(install_location):
                exe_files = self.find_exe_in_directory(install_location)
                if exe_files:
                    # Фильтруем мусорные пути
                    valid_files = [f for f in exe_files if not self.is_trash_path(f)]
                    if valid_files:
                        return valid_files[0]
        except (FileNotFoundError, OSError):
            pass

        # Пробуем получить из UninstallString
        try:
            uninstall_string = winreg.QueryValueEx(subkey, "UninstallString")[0]
            if uninstall_string:
                # Ищем основной exe вместо uninstall
                main_path = self.convert_uninstall_to_main_path(uninstall_string, display_name)
                if main_path:
                    return main_path
        except (FileNotFoundError, OSError):
            pass

        # Пытаемся угадать путь
        return self.guess_exe_path(display_name)

    def convert_uninstall_to_main_path(self, uninstall_string: str, program_name: str) -> Optional[str]:
        """Преобразует путь uninstall в путь основной программы"""
        # Извлекаем путь из строки
        path_match = re.search(r'["\']([^"\']+\.exe)["\']', uninstall_string, re.IGNORECASE)
        if not path_match:
            path_match = re.search(r'([A-Za-z]:\\[^\s]+\.exe)', uninstall_string, re.IGNORECASE)

        if not path_match:
            return None

        uninstall_path = path_match.group(1)

        # Проверяем не является ли это мусорный путь
        if self.is_trash_path(uninstall_path):
            # Ищем основной exe в той же директории
            path_obj = Path(uninstall_path)
            if path_obj.parent.exists():
                # Ищем exe файлы с похожим именем
                base_name = self.extract_base_name(program_name)
                if base_name:
                    for file in path_obj.parent.glob('*.exe'):
                        file_base = self.extract_base_name(file.stem)
                        if file_base and base_name.lower() in file_base.lower():
                            if not self.is_trash_path(str(file)):
                                return str(file)

                # Ищем любой подходящий exe
                exe_files = self.find_exe_in_directory(str(path_obj.parent))
                valid_files = [f for f in exe_files if not self.is_trash_path(f)]
                if valid_files:
                    return valid_files[0]

        return uninstall_path

    def find_exe_in_directory(self, directory: str, max_files: int = 5) -> List[str]:
        """Ищет exe файлы в директории"""
        exe_files = []
        try:
            for root, dirs, files in os.walk(directory):
                # Пропускаем системные директории
                dirs[:] = [d for d in dirs if d.lower() not in {
                    'uninstall', 'installer', 'setup', 'temp', 'cache',
                    'logs', 'backup', 'old', 'update', 'crash'
                }]

                for file in files:
                    if file.lower().endswith('.exe'):
                        full_path = os.path.join(root, file)
                        # Проверяем не мусорный ли это файл
                        if not self.is_trash_path(full_path):
                            exe_files.append(full_path)
                            if len(exe_files) >= max_files:
                                return exe_files
        except (OSError, PermissionError):
            pass
        return exe_files

    def guess_exe_path(self, program_name: str) -> str:
        """Пытается угадать путь на основе названия программы"""
        username = os.getenv('USERNAME', '')
        base_name = self.extract_base_name(program_name)

        # Распространенные пути
        common_paths = {
            'steam': r'C:\Program Files (x86)\Steam\Steam.exe',
            'chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            'firefox': r'C:\Program Files\Mozilla Firefox\firefox.exe',
            'edge': r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            'pycharm': r'C:\Program Files\JetBrains\PyCharm*\bin\pycharm64.exe',
            'qbittorrent': r'C:\Program Files\qBittorrent\qbittorrent.exe',
            'cpu-z': r'C:\Program Files\CPUID\CPU-Z*\cpuz.exe',
            'wiztree': r'C:\Program Files\WizTree\WizTree.exe',
            'yandex': rf'C:\Users\{username}\AppData\Local\Yandex\YandexBrowser\Application\browser.exe',
            'telegram': rf'C:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe',
            'discord': rf'C:\Users\{username}\AppData\Local\Discord\app-*\Discord.exe',
            'vlc': r'C:\Program Files\VideoLAN\VLC\vlc.exe',
            'notepad++': r'C:\Program Files\Notepad++\notepad++.exe',
            'audacity': r'C:\Program Files\Audacity\Audacity.exe',
            'handbrake': r'C:\Program Files\HandBrake\HandBrake.exe',
            'sharex': r'C:\Program Files\ShareX\ShareX.exe',
            'everything': r'C:\Program Files\Everything\Everything.exe',
            'valorant': r'C:\My_App\Riot Games\VALORANT\live\VALORANT.exe',
            'riot client': r'C:\My_App\Riot Games\Riot Client\RiotClientServices.exe',
        }

        name_lower = base_name.lower()

        for key, path in common_paths.items():
            if key in name_lower:
                # Обрабатываем wildcards
                if '*' in path:
                    import glob
                    matches = glob.glob(path)
                    if matches:
                        return matches[0]
                elif os.path.exists(path):
                    return path

        # Поиск в стандартных директориях
        search_dirs = [
            Path(r'C:\Program Files'),
            Path(r'C:\Program Files (x86)'),
            Path(rf'C:\Users\{username}\AppData\Local'),
            Path(rf'C:\Users\{username}\AppData\Roaming'),
        ]

        # Ищем похожие названия
        if base_name:
            search_terms = [base_name.lower()]
            # Добавляем первые слова если название длинное
            words = base_name.lower().split()
            if len(words) > 1:
                search_terms.append(words[0])

            for search_dir in search_dirs:
                if search_dir.exists():
                    try:
                        for item in search_dir.iterdir():
                            if item.is_dir():
                                item_name = self.normalize_program_name(item.name)
                                if any(term in item_name for term in search_terms):
                                    exe_files = self.find_exe_in_directory(str(item), max_files=1)
                                    if exe_files:
                                        return exe_files[0]
                    except (OSError, PermissionError):
                        continue

        return "❓ Путь не найден"

    def generate_pronunciation_variants(self, program_name: str) -> List[str]:
        """Генерирует варианты произношения для программы"""
        variants = set()
        base_name = self.extract_base_name(program_name)

        # Проверяем популярные программы
        name_lower = program_name.lower()
        for popular_name, popular_data in self.popular_programs.items():
            if popular_name in name_lower:
                variants.update(popular_data['ru'])

        # Транслитерируем название
        transliterated = self.transliterate_name(base_name)
        if transliterated:
            variants.add(transliterated)

        # Добавляем оригинальное название
        variants.add(base_name.lower())

        # Генерируем комбинации слов
        words = base_name.lower().split()
        if len(words) > 1:
            # Комбинации из первых букв
            abbreviation = ''.join(word[0] for word in words if word)
            variants.add(abbreviation)

            # Транслитерация каждого слова
            transliterated_words = []
            for word in words:
                word_translit = self.transliterate_name(word)
                if word_translit:
                    transliterated_words.append(word_translit)

            if transliterated_words:
                variants.add(' '.join(transliterated_words))

        # Фильтруем и сортируем
        filtered = [v for v in variants if v and len(v) >= 2]
        return sorted(filtered, key=lambda x: (len(x), x))[:10]

    def transliterate_name(self, name: str) -> Optional[str]:
        """Транслитерирует название с английского на русский"""
        result = name.lower()
        result = re.sub(r'[^\w\s]', '', result)

        # Применяем транслитерацию
        for eng, rus in self.translit_dict.items():
            result = result.replace(eng, rus)

        # Если результат отличается от оригинала возвращаем его
        if result != name.lower():
            return result
        return None

    def scan_registry(self) -> List[Dict]:
        """Сканирует реестр Windows для поиска программ"""
        programs = []

        for hive, hive_name in self.registry_hives:
            for registry_path in self.registry_paths:
                try:
                    key = winreg.OpenKey(hive, registry_path)
                    logger.info(f"Сканирую: {hive_name}\\{registry_path}")

                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)

                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]

                                # Пропускаем системные компоненты
                                if self.is_system_component(display_name):
                                    continue

                                # Получаем путь к exe
                                exe_path = self.find_exe_path(subkey, display_name)

                                # Пропускаем мусорные пути
                                if self.is_trash_path(exe_path):
                                    continue

                                # Определяем категорию
                                category = self.get_program_category(display_name)

                                # Генерируем варианты произношения
                                pronunciation = self.generate_pronunciation_variants(display_name)

                                programs.append({
                                    'name': display_name,
                                    'path': exe_path,
                                    'pronunciation': pronunciation,
                                    'category': category,
                                    'source': f"{hive_name}\\{registry_path}",
                                    'base_name': self.extract_base_name(display_name)
                                })

                            except (FileNotFoundError, OSError):
                                pass
                            except Exception as e:
                                logger.debug(f"Ошибка чтения подключа {subkey_name}: {e}")

                            winreg.CloseKey(subkey)

                        except (FileNotFoundError, OSError):
                            continue
                        except Exception as e:
                            logger.debug(f"Ошибка обработки подключа: {e}")

                    winreg.CloseKey(key)

                except (FileNotFoundError, OSError):
                    logger.debug(f"Раздел реестра не найден: {hive_name}\\{registry_path}")
                except Exception as e:
                    logger.warning(f"Ошибка доступа к {hive_name}\\{registry_path}: {e}")

        return programs

    def find_manual_programs(self) -> List[Dict]:
        """Ищет программы вручную в стандартных местах установки"""
        logger.info("Выполняю ручной поиск программ...")
        programs = []
        username = os.getenv('USERNAME', '')

        # Словарь программ для ручного поиска
        manual_locations = {
            'Yandex Browser': [
                rf'C:\Users\{username}\AppData\Local\Yandex\YandexBrowser\Application\browser.exe',
                r'C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe',
                r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe',
            ],
            'Telegram': [
                rf'C:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe',
                r'C:\Program Files\Telegram Desktop\Telegram.exe',
                r'C:\Program Files (x86)\Telegram Desktop\Telegram.exe',
            ],
            'Discord': [
                rf'C:\Users\{username}\AppData\Local\Discord\Discord.exe',
                r'C:\Program Files\Discord\Discord.exe',
            ],
            'Steam': [
                r'C:\Program Files (x86)\Steam\Steam.exe',
                r'C:\Program Files\Steam\Steam.exe',
            ],
            'Spotify': [
                rf'C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe',
                r'C:\Program Files\Spotify\Spotify.exe',
            ],
            'VLC': [
                r'C:\Program Files\VideoLAN\VLC\vlc.exe',
                r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
            ],
            'Notepad++': [
                r'C:\Program Files\Notepad++\notepad++.exe',
                r'C:\Program Files (x86)\Notepad++\notepad++.exe',
            ],
            'qBittorrent': [
                r'C:\Program Files\qBittorrent\qbittorrent.exe',
                r'C:\Program Files (x86)\qBittorrent\qbittorrent.exe',
            ],
            'Audacity': [
                r'C:\Program Files\Audacity\Audacity.exe',
                r'C:\Program Files (x86)\Audacity\Audacity.exe',
            ],
            'HandBrake': [
                r'C:\Program Files\HandBrake\HandBrake.exe',
                r'C:\Program Files (x86)\HandBrake\HandBrake.exe',
            ],
        }

        for program_name, paths in manual_locations.items():
            for path in paths:
                if os.path.exists(path) and not self.is_trash_path(path):
                    logger.info(f"Найдена программа: {program_name} -> {path}")
                    programs.append({
                        'name': program_name,
                        'path': path,
                        'pronunciation': self.generate_pronunciation_variants(program_name),
                        'category': self.get_program_category(program_name),
                        'source': 'manual_search',
                        'base_name': self.extract_base_name(program_name)
                    })
                    break

        return programs

    def scan_start_menu(self) -> List[Dict]:
        """Сканирует меню Пуск для поиска ярлыков программ"""
        logger.info("Сканирую меню Пуск...")
        programs = []
        username = os.getenv('USERNAME', '')

        # Директории с ярлыками
        start_menu_dirs = [
            Path(r'C:\ProgramData\Microsoft\Windows\Start Menu\Programs'),
            Path(rf'C:\Users\{username}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs'),
        ]

        for start_dir in start_menu_dirs:
            if not start_dir.exists():
                continue

            try:
                for shortcut in start_dir.rglob('*.lnk'):
                    try:
                        # Используем PowerShell для получения информации о ярлыке
                        ps_command = f"""
                        $shell = New-Object -ComObject WScript.Shell
                        $shortcut = $shell.CreateShortcut('{shortcut}')
                        Write-Output "$($shortcut.TargetPath)"
                        """

                        result = subprocess.run(
                            ['powershell', '-Command', ps_command],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )

                        if result.returncode == 0 and result.stdout.strip():
                            target_path = result.stdout.strip()
                            if target_path and os.path.exists(target_path) and target_path.lower().endswith('.exe'):
                                program_name = shortcut.stem

                                # Пропускаем системные и служебные программы
                                if self.is_system_component(program_name):
                                    continue

                                # Пропускаем мусорные пути
                                if self.is_trash_path(target_path):
                                    continue

                                programs.append({
                                    'name': program_name,
                                    'path': target_path,
                                    'pronunciation': self.generate_pronunciation_variants(program_name),
                                    'category': self.get_program_category(program_name),
                                    'source': 'start_menu',
                                    'base_name': self.extract_base_name(program_name)
                                })
                    except Exception as e:
                        logger.debug(f"Ошибка обработки ярлыка {shortcut}: {e}")

            except (OSError, PermissionError) as e:
                logger.debug(f"Ошибка доступа к {start_dir}: {e}")

        return programs

    def is_duplicate(self, prog1: Dict, prog2: Dict) -> bool:
        """Проверяет являются ли две программы дубликатами"""
        name1 = self.normalize_program_name(prog1.get('base_name', prog1['name']))
        name2 = self.normalize_program_name(prog2.get('base_name', prog2['name']))

        # Если имена пустые или слишком короткие
        if len(name1) < 3 or len(name2) < 3:
            return False

        # Проверяем полное совпадение
        if name1 == name2:
            return True

        # Проверяем частичное совпадение
        if name1 in name2 or name2 in name1:
            return True

        # Проверяем совпадение путей
        path1 = prog1.get('path', '').lower()
        path2 = prog2.get('path', '').lower()

        if path1 and path2 and path1 != '❓ путь не найден' and path2 != '❓ путь не найден':
            # Если пути одинаковые
            if path1 == path2:
                return True

            # Если пути ведут в одну директорию
            dir1 = str(Path(path1).parent).lower()
            dir2 = str(Path(path2).parent).lower()
            if dir1 == dir2:
                return True

        return False

    def deduplicate_programs(self, programs: List[Dict]) -> List[Dict]:
        """Удаляет дубликаты программ оставляя лучшую версию"""
        unique_programs = []

        for program in programs:
            is_dup = False

            for i, existing in enumerate(unique_programs):
                if self.is_duplicate(program, existing):
                    # Выбираем лучшую версию
                    if self.is_better_program(program, existing):
                        unique_programs[i] = program
                    is_dup = True
                    break

            if not is_dup:
                unique_programs.append(program)

        return unique_programs

    def is_better_program(self, prog1: Dict, prog2: Dict) -> bool:
        """Определяет какая версия программы лучше"""
        score1 = self.score_program(prog1)
        score2 = self.score_program(prog2)
        return score1 > score2

    def score_program(self, program: Dict) -> float:
        """Оценивает качество программы для выбора лучшей версии"""
        score = 0.0

        # Путь найден
        if not program['path'].startswith('❓'):
            score += 10

        # Не мусорный путь
        if not self.is_trash_path(program['path']):
            score += 5

        # Источник: реестр лучше чем ручной поиск
        source = program.get('source', '').lower()
        if 'registry' in source:
            score += 3
        elif 'manual' in source:
            score += 2
        elif 'start_menu' in source:
            score += 1

        # Больше вариантов произношения
        score += len(program.get('pronunciation', [])) * 0.5

        # Название без версии (более общее)
        if any(char.isdigit() for char in program['name']):
            score -= 2

        # Название короче (более чистое)
        score -= len(program['name']) * 0.1

        # Базовое имя совпадает с полным (значит нет лишних слов)
        base_name = program.get('base_name', '')
        if base_name and base_name.lower() == program['name'].lower():
            score += 3

        return score

    def scan_all(self) -> Dict:
        """Выполняет полное сканирование всех программ"""
        logger.info("Начинаю полное сканирование программ...")

        # Собираем программы из всех источников
        all_programs = []

        # Сканирование реестра
        registry_programs = self.scan_registry()
        all_programs.extend(registry_programs)
        logger.info(f"Найдено в реестре: {len(registry_programs)}")

        # Ручной поиск
        manual_programs = self.find_manual_programs()
        all_programs.extend(manual_programs)
        logger.info(f"Найдено вручную: {len(manual_programs)}")

        # Сканирование меню Пуск
        start_menu_programs = self.scan_start_menu()
        all_programs.extend(start_menu_programs)
        logger.info(f"Найдено в меню Пуск: {len(start_menu_programs)}")

        # Удаляем дубликаты
        unique_programs = self.deduplicate_programs(all_programs)
        logger.info(f"Всего уникальных программ: {len(unique_programs)}")

        # Сортируем по категориям
        programs_by_category = defaultdict(dict)
        category_counts = defaultdict(int)

        for program in unique_programs:
            category = program['category']
            clean_key = re.sub(r'[^\w\s]', '', program['name']).lower().replace(' ', '_')

            programs_by_category[category][clean_key] = {
                "display_name": program['name'],
                "exe_path": program['path'],
                "pronunciation_variants": program['pronunciation'],
                "category": category
            }
            category_counts[category] += 1

        # Создаем структуру данных
        database = {
            "metadata": {
                "scan_date": datetime.now().isoformat(),
                "scan_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_programs": len(unique_programs),
                "categories": dict(category_counts)
            },
            "programs": dict(programs_by_category)
        }

        return database

    def save_database(self, database: Dict) -> bool:
        """Сохраняет базу программ в JSON файл"""
        try:
            # Создаем директорию если её нет
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Сохраняем в JSON
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(database, f, ensure_ascii=False, indent=2, sort_keys=True)

            logger.info(f"База программ сохранена в {self.output_file}")
            logger.info(f"Всего программ: {database['metadata']['total_programs']}")

            # Выводим статистику по категориям
            for category, count in database['metadata']['categories'].items():
                logger.info(f"  {category}: {count} программ")

            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения базы: {e}")
            return False

    def load_database(self) -> Optional[Dict]:
        """Загружает базу программ из JSON файла"""
        try:
            if not self.output_file.exists():
                logger.warning(f"Файл {self.output_file} не найден")
                return None

            with open(self.output_file, 'r', encoding='utf-8') as f:
                database = json.load(f)

            logger.info(f"База программ загружена: {database['metadata']['total_programs']} программ")
            return database

        except Exception as e:
            logger.error(f"Ошибка загрузки базы: {e}")
            return None

    def find_program(self, query: str) -> Optional[Dict]:
        """Ищет программу по названию или варианту произношения"""
        database = self.load_database()
        if not database:
            return None

        query_lower = query.lower()

        # Сначала проверяем точные совпадения
        for category, programs in database['programs'].items():
            for program_key, program_data in programs.items():
                # Проверяем точное совпадение названия
                if program_data['display_name'].lower() == query_lower:
                    return program_data

                # Проверяем варианты произношения
                for variant in program_data['pronunciation_variants']:
                    if variant.lower() == query_lower:
                        return program_data

        # Затем проверяем частичные совпадения
        best_match = None
        best_score = 0

        for category, programs in database['programs'].items():
            for program_key, program_data in programs.items():
                # Проверяем название
                if query_lower in program_data['display_name'].lower():
                    score = len(query_lower) / len(program_data['display_name'])
                    if score > best_score:
                        best_match = program_data
                        best_score = score

                # Проверяем варианты произношения
                for variant in program_data['pronunciation_variants']:
                    if query_lower in variant.lower():
                        score = len(query_lower) / len(variant)
                        if score > best_score:
                            best_match = program_data
                            best_score = score

        return best_match

    def launch_program(self, program_data: Dict) -> Tuple[bool, str]:
        """Запускает программу"""
        exe_path = program_data.get('exe_path', '')

        if not exe_path or exe_path.startswith('❓'):
            return False, f"Не удалось найти путь для запуска {program_data.get('display_name', 'программы')}"

        try:
            os.startfile(exe_path)
            return True, f"Запускаю {program_data.get('display_name', 'программу')}"
        except Exception as e:
            return False, f"Ошибка запуска {program_data.get('display_name', 'программы')}: {str(e)}"


def main():
    """Основная функция для запуска сканирования"""
    scanner = ProgramScanner()

    print("🚀 Запуск сканирования программ...")
    print("=" * 50)

    database = scanner.scan_all()

    if scanner.save_database(database):
        print("=" * 50)
        print("✅ Сканирование завершено успешно!")

        # Выводим список найденных программ
        print("\n📋 Найденные программы:")
        for category, programs in database['programs'].items():
            print(f"\n{category}:")
            for program_key, program_data in programs.items():
                print(f"  • {program_data['display_name']}")
                if not program_data['exe_path'].startswith('❓'):
                    print(f"    📂 {program_data['exe_path']}")
    else:
        print("=" * 50)
        print("❌ Ошибка при сканировании или сохранении")


if __name__ == "__main__":
    main()