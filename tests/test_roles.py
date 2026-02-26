"""
Тесты для системы ролей пользователей

Проверяет:
- Создание и миграцию ролей
- Проверку прав доступа
- Функции управления ролями

Дата: 2026-02-26
"""

import pytest
import sqlite3
import os
import sys
from pathlib import Path

# Добавляем родительскую директорию в path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Константы
DB_PATH = Path(__file__).parent.parent / "data" / "test_bot.db"
ADMIN_ID = 999999999  # Тестовый ID админа


class TestRolesModule:
    """Тесты модуля roles.py"""

    @pytest.fixture(autouse=True)
    def setup_database(self, tmp_path):
        """Создать тестовую БД перед каждым тестом"""
        db_file = tmp_path / "test_bot.db"

        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Создать таблицу users с колонкой role
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                telegram_username VARCHAR(255),
                telegram_first_name VARCHAR(255),
                user_type VARCHAR(20) DEFAULT 'private',
                role VARCHAR(20) DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        # Создать тестового админа
        cursor.execute(
            "INSERT INTO users (telegram_id, telegram_username, role) VALUES (?, ?, ?)",
            (ADMIN_ID, "admin", "admin")
        )

        # Создать тестового менеджера
        cursor.execute(
            "INSERT INTO users (telegram_id, telegram_username, role) VALUES (?, ?, ?)",
            (123456, "manager", "manager")
        )

        # Создать тестового пользователя
        cursor.execute(
            "INSERT INTO users (telegram_id, telegram_username, role) VALUES (?, ?, ?)",
            (789012, "user", "user")
        )

        conn.commit()
        conn.close()

        # Подменяем DB_PATH для тестов
        import scripts.roles as roles_module
        original_db_path = roles_module.DB_PATH
        roles_module.DB_PATH = db_file

        yield db_file

        # Восстанавливаем оригинальный путь
        roles_module.DB_PATH = original_db_path

    def test_get_user_role_admin(self, setup_database):
        """Тест: Получение роли админа"""
        from scripts.roles import get_user_role, Role

        role = get_user_role(ADMIN_ID)
        assert role == Role.ADMIN

    def test_get_user_role_manager(self, setup_database):
        """Тест: Получение роли менеджера"""
        from scripts.roles import get_user_role, Role

        role = get_user_role(123456)
        assert role == Role.MANAGER

    def test_get_user_role_user(self, setup_database):
        """Тест: Получение роли пользователя"""
        from scripts.roles import get_user_role, Role

        role = get_user_role(789012)
        assert role == Role.USER

    def test_get_user_role_unknown_user(self, setup_database):
        """Тест: Неизвестный пользователь получает роль USER"""
        from scripts.roles import get_user_role, Role

        role = get_user_role(999999888)
        assert role == Role.USER  # Fallback на роль по умолчанию

    def test_is_admin(self, setup_database):
        """Тест: Проверка is_admin"""
        from scripts.roles import is_admin

        assert is_admin(ADMIN_ID) == True
        assert is_admin(123456) == False
        assert is_admin(789012) == False

    def test_is_manager(self, setup_database):
        """Тест: Проверка is_manager"""
        from scripts.roles import is_manager

        assert is_manager(ADMIN_ID) == True  # Admin тоже менеджер
        assert is_manager(123456) == True
        assert is_manager(789012) == False

    def test_can_invite_users(self, setup_database):
        """Тест: Проверка прав на приглашение"""
        from scripts.roles import can_invite_users

        assert can_invite_users(ADMIN_ID) == True
        assert can_invite_users(123456) == True
        assert can_invite_users(789012) == False

    def test_set_user_role(self, setup_database):
        """Тест: Установка роли пользователю"""
        from scripts.roles import set_user_role, Role, get_user_role

        # Повысить пользователя до менеджера
        result = set_user_role(789012, Role.MANAGER)
        assert result == True

        # Проверить что роль изменилась
        role = get_user_role(789012)
        assert role == Role.MANAGER

    def test_get_role_display_name(self, setup_database):
        """Тест: Отображаемые имена ролей"""
        from scripts.roles import get_role_display_name, Role

        assert get_role_display_name(Role.USER) == "Пользователь"
        assert get_role_display_name(Role.MANAGER) == "Менеджер"
        assert get_role_display_name(Role.ADMIN) == "Администратор"

    def test_get_users_by_role(self, setup_database):
        """Тест: Получение пользователей по роли"""
        from scripts.roles import get_users_by_role, Role

        # Получить всех менеджеров
        managers = get_users_by_role(Role.MANAGER)
        assert len(managers) == 1
        assert managers[0]['telegram_id'] == 123456
        assert managers[0]['telegram_username'] == "manager"


class TestRoleIntegration:
    """Интеграционные тесты для системы ролей"""

    @pytest.fixture(autouse=True)
    def setup_database(self, tmp_path):
        """Создать тестовую БД"""
        db_file = tmp_path / "test_bot.db"

        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                telegram_username VARCHAR(255),
                role VARCHAR(20) DEFAULT 'user'
            )
        ''')

        conn.commit()
        conn.close()

        import scripts.roles as roles_module
        original_db_path = roles_module.DB_PATH
        roles_module.DB_PATH = db_file

        yield db_file

        roles_module.DB_PATH = original_db_path

    def test_user_creation_has_default_role(self, setup_database):
        """Тест: При создании пользователя роль устанавливается в 'user'"""
        from scripts.roles import get_user_role, Role

        # Создать нового пользователя (эмуляция)
        conn = sqlite3.connect(setup_database)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, telegram_username) VALUES (?, ?)",
            (111222, "newuser")
        )
        conn.commit()
        conn.close()

        # Проверить что роль = 'user' по умолчанию
        role = get_user_role(111222)
        assert role == Role.USER

    def test_role_upgrade_workflow(self, setup_database):
        """Тест: Workflow повышения прав пользователя"""
        from scripts.roles import (
            get_user_role, set_user_role, is_admin,
            is_manager, can_invite_users, Role
        )

        user_id = 333444

        # 1. Создать пользователя
        conn = sqlite3.connect(setup_database)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, telegram_username) VALUES (?, ?)",
            (user_id, "promote_user")
        )
        conn.commit()
        conn.close()

        # 2. Проверить начальную роль
        assert get_user_role(user_id) == Role.USER
        assert is_admin(user_id) == False
        assert is_manager(user_id) == False
        assert can_invite_users(user_id) == False

        # 3. Повысить до менеджера
        set_user_role(user_id, Role.MANAGER)

        # 4. Проверить новые права
        assert get_user_role(user_id) == Role.MANAGER
        assert is_admin(user_id) == False
        assert is_manager(user_id) == True
        assert can_invite_users(user_id) == True

        # 5. Повысить до админа
        set_user_role(user_id, Role.ADMIN)

        # 6. Проверить финальные права
        assert get_user_role(user_id) == Role.ADMIN
        assert is_admin(user_id) == True
        assert is_manager(user_id) == True
        assert can_invite_users(user_id) == True


class TestRoleEnum:
    """Тесты enum Role"""

    def test_role_values(self):
        """Тест: Значения ролей"""
        from scripts.roles import Role

        assert Role.USER.value == "user"
        assert Role.MANAGER.value == "manager"
        assert Role.ADMIN.value == "admin"

    def test_role_from_string_valid(self):
        """Тест: Преобразование строки в Role (валидные значения)"""
        from scripts.roles import Role

        assert Role.from_string("user") == Role.USER
        assert Role.from_string("manager") == Role.MANAGER
        assert Role.from_string("admin") == Role.ADMIN
        assert Role.from_string("USER") == Role.USER  # Верхний регистр
        assert Role.from_string("User") == Role.USER  # С заглавной

    def test_role_from_string_invalid(self):
        """Тест: Преобразование строки в Role (невалидные значения)"""
        from scripts.roles import Role

        # Невалидные значения возвращают USER по умолчанию
        assert Role.from_string("invalid") == Role.USER
        assert Role.from_string("") == Role.USER
        assert Role.from_string("superadmin") == Role.USER


class TestMigration:
    """Тесты миграции БД"""

    def test_migration_sql_exists(self):
        """Тест: Файл миграции существует"""
        migration_file = Path(__file__).parent.parent / "migrations" / "v3.1_add_roles.sql"
        assert migration_file.exists()

    def test_migration_sql_content(self):
        """Тест: Проверка содержимого файла миграции"""
        migration_file = Path(__file__).parent.parent / "migrations" / "v3.1_add_roles.sql"
        content = migration_file.read_text()

        # Проверить ключевые слова
        assert "ALTER TABLE users ADD COLUMN role" in content
        assert "CREATE INDEX IF NOT EXISTS idx_users_role" in content
        assert "DEFAULT 'user'" in content


def test_role_fallback_without_module():
    """Тест: Fallback поведение если модуль ролей не доступен"""
    # Этот тест проверяет что бот работает без модуля ролей
    # с обратной совместимостью

    # Проверяем что если Roles = None, код не падает
    from scripts import monitor_bot

    # Если модуль ролей не загрузился, Role будет None
    if monitor_bot.Role is None:
        # is_admin должен использовать fallback
        test_admin_id = 999999999
        # Это не должно вызывать ошибку
        result = monitor_bot.is_admin(test_admin_id)
        # При fallback просто сравнивает с ADMIN_ID
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
