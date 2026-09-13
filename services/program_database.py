"""
Сервис базы данных программ
Содержит функции для работы с базой данных установленных программ
"""

import os
import json
import logging
import subprocess
from typing import Optional, Dict, List, Tuple

from config import PROGRAMS_DATABASE_FILE

logger = logging.getLogger(__name__)


class ProgramDatabase:
    """
    Класс для работы с базой данных программ
    """

    def __init__(self):
        """Инициализация базы данных программ"""
        self.programs_db = self.load()

    def load(self) -> Dict:
        """
        Загружает базу данных программ из JSON файла

        Returns:
            Dict: База данных программ
        """
        try:
            if os.path.exists(PROGRAMS_DATABASE_FILE):
                with open(PROGRAMS_DATABASE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"загружена база данных программ: {len(data.get('programs', {}))} категорий")
                    return data
            else:
                logger.warning("файл базы данных программ не найден")
                return {"programs": {}, "metadata": {}}
        except Exception as e:
            logger.error(f"ошибка загрузки базы данных программ: {e}")
            return {"programs": {}, "metadata": {}}

    def save(self) -> bool:
        """
        Сохраняет базу данных программ в JSON файл

        Returns:
            bool: True если успешно сохранено
        """
        try:
            with open(PROGRAMS_DATABASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.programs_db, f, ensure_ascii=False, indent=2)
            logger.info("база данных программ сохранена")
            return True
        except Exception as e:
            logger.error(f"ошибка сохранения базы данных программ: {e}")
            return False

    def update(self) -> str:
        """
        Запускает скрипт обновления базы данных программ

        Returns:
            str: Результат обновления
        """
        try:
            logger.info("🔄 запуск обновления базы данных программ")

            # Ищем скрипт обновления
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'program_scripts.py')

            if not os.path.exists(script_path):
                logger.error(f"скрипт обновления не найден: {script_path}")
                return "скрипт обновления не найден"

            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8'
            )

            if result.returncode == 0:
                logger.info("✅ база данных программ успешно обновлена")
                # Перезагружаем базу данных
                self.programs_db = self.load()
                return "база данных программ успешно обновлена"
            else:
                logger.error(f"❌ ошибка обновления базы данных: {result.stderr}")
                return f"ошибка обновления: {result.stderr}"

        except subprocess.TimeoutExpired:
            logger.error("таймаут при обновлении базы данных")
            return "таймаут при обновлении базы данных"
        except Exception as e:
            logger.error(f"ошибка при обновлении базы данных: {e}")
            return f"ошибка: {e}"

    def find_program_by_name(self, command: str, is_close_command: bool = False) -> Optional[Dict]:
        """
        Ищет программу в базе данных по команде

        Args:
            command (str): Команда для поиска
            is_close_command (bool): Является ли командой закрытия

        Returns:
            Optional[Dict]: Информация о программе или None
        """
        programs = self.programs_db.get("programs", {})

        command_lower = command.lower()

        # Если это команда закрытия, убираем ключевые слова закрытия
        if is_close_command:
            close_keywords = ['закрой', 'выключи', 'заверши', 'закрыть', 'выключить', 'отключи']
            for keyword in close_keywords:
                command_lower = command_lower.replace(keyword, '').strip()

        best_match = None
        best_score = 0

        # Ищем по всем категориям и программам
        for category, category_programs in programs.items():
            if not isinstance(category_programs, dict):
                continue

            for program_id, program_info in category_programs.items():
                if not isinstance(program_info, dict):
                    continue

                score = 0

                # Проверяем название программы
                display_name = program_info.get("display_name", "").lower()
                if display_name and display_name in command_lower:
                    score += 3

                # Проверяем варианты произношения
                pronunciation_variants = program_info.get("pronunciation_variants", [])
                for variant in pronunciation_variants:
                    variant_lower = variant.lower()
                    if variant_lower in command_lower:
                        score += 2
                        # Если точное совпадение, максимальный балл
                        if command_lower == variant_lower:
                            score += 5

                # Проверяем ключевые слова
                keywords = program_info.get("keywords", [])
                for keyword in keywords:
                    if keyword.lower() in command_lower:
                        score += 1

                # Проверяем id программы
                if program_id.lower() in command_lower:
                    score += 2

                if score > best_score:
                    best_score = score
                    best_match = program_info

        # Если нашли хорошее совпадение, возвращаем его
        if best_score >= 2:
            logger.info(f"найдена программа: {best_match.get('display_name', 'Unknown')} (очки: {best_score})")
            return best_match

        return None

    def get_program_by_exe_path(self, exe_path: str) -> Optional[Dict]:
        """
        Ищет программу по пути к исполняемому файлу

        Args:
            exe_path (str): Путь к исполняемому файлу

        Returns:
            Optional[Dict]: Информация о программе или None
        """
        programs = self.programs_db.get("programs", {})

        for category, category_programs in programs.items():
            if not isinstance(category_programs, dict):
                continue

            for program_id, program_info in category_programs.items():
                if not isinstance(program_info, dict):
                    continue

                if program_info.get("exe_path", "").lower() == exe_path.lower():
                    return program_info

        return None

    def get_all_programs(self) -> List[Dict]:
        """
        Возвращает список всех программ

        Returns:
            List[Dict]: Список программ
        """
        programs = []

        for category, category_programs in self.programs_db.get("programs", {}).items():
            if not isinstance(category_programs, dict):
                continue

            for program_id, program_info in category_programs.items():
                if isinstance(program_info, dict):
                    program_info['category'] = category
                    program_info['id'] = program_id
                    programs.append(program_info)

        return programs

    def get_categories(self) -> List[str]:
        """
        Возвращает список категорий программ

        Returns:
            List[str]: Список категорий
        """
        return list(self.programs_db.get("programs", {}).keys())

    def get_programs_by_category(self, category: str) -> List[Dict]:
        """
        Возвращает программы из указанной категории

        Args:
            category (str): Название категории

        Returns:
            List[Dict]: Список программ в категории
        """
        programs = []
        category_programs = self.programs_db.get("programs", {}).get(category, {})

        if isinstance(category_programs, dict):
            for program_id, program_info in category_programs.items():
                if isinstance(program_info, dict):
                    program_info['id'] = program_id
                    programs.append(program_info)

        return programs

    def add_program(self, category: str, program_info: Dict) -> bool:
        """
        Добавляет программу в базу данных

        Args:
            category (str): Категория программы
            program_info (Dict): Информация о программе

        Returns:
            bool: True если успешно добавлено
        """
        try:
            if "programs" not in self.programs_db:
                self.programs_db["programs"] = {}

            if category not in self.programs_db["programs"]:
                self.programs_db["programs"][category] = {}

            # Генерируем ID если не указан
            if "id" not in program_info:
                program_id = f"program_{len(self.programs_db['programs'][category]) + 1}"
            else:
                program_id = program_info.pop("id")

            self.programs_db["programs"][category][program_id] = program_info

            return self.save()
        except Exception as e:
            logger.error(f"ошибка добавления программы: {e}")
            return False

    def remove_program(self, program_id: str, category: Optional[str] = None) -> bool:
        """
        Удаляет программу из базы данных

        Args:
            program_id (str): ID программы
            category (str, optional): Категория программы

        Returns:
            bool: True если успешно удалено
        """
        try:
            if category:
                if category in self.programs_db.get("programs", {}):
                    if program_id in self.programs_db["programs"][category]:
                        del self.programs_db["programs"][category][program_id]
                        return self.save()
            else:
                # Ищем во всех категориях
                for cat, programs in self.programs_db.get("programs", {}).items():
                    if isinstance(programs, dict) and program_id in programs:
                        del self.programs_db["programs"][cat][program_id]
                        return self.save()

            logger.warning(f"программа не найдена: {program_id}")
            return False
        except Exception as e:
            logger.error(f"ошибка удаления программы: {e}")
            return False

    def search_programs(self, query: str) -> List[Dict]:
        """
        Поиск программ по запросу

        Args:
            query (str): Поисковый запрос

        Returns:
            List[Dict]: Найденные программы
        """
        results = []
        query_lower = query.lower()

        for program in self.get_all_programs():
            # Проверяем название
            if query_lower in program.get("display_name", "").lower():
                results.append(program)
                continue

            # Проверяем ключевые слова
            if any(query_lower in kw.lower() for kw in program.get("keywords", [])):
                results.append(program)
                continue

            # Проверяем варианты произношения
            if any(query_lower in variant.lower() for variant in program.get("pronunciation_variants", [])):
                results.append(program)

        return results

    def get_database_stats(self) -> Dict:
        """
        Возвращает статистику базы данных

        Returns:
            Dict: Статистика базы данных
        """
        programs = self.get_all_programs()
        categories = self.get_categories()

        return {
            'total_programs': len(programs),
            'total_categories': len(categories),
            'categories': {cat: len(self.get_programs_by_category(cat)) for cat in categories},
            'last_updated': self.programs_db.get("metadata", {}).get("last_updated", "неизвестно")
        }


# Создаем глобальный экземпляр
program_database = ProgramDatabase()


# Функции для обратной совместимости
def load_programs_database() -> Dict:
    """Обертка для загрузки базы данных"""
    return program_database.load()


def update_programs_database() -> str:
    """Обертка для обновления базы данных"""
    return program_database.update()


def find_program_by_name(command: str, is_close_command: bool = False) -> Optional[Dict]:
    """Обертка для поиска программы"""
    return program_database.find_program_by_name(command, is_close_command)