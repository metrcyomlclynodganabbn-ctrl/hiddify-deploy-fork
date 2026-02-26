"""
Система ролей пользователей Hiddify VPN Bot

Роли:
- USER: обычный пользователь
- MANAGER: менеджер (может приглашать, видеть статистику)
- ADMIN: администратор (полные права)

Дата: 2026-02-26
"""

from enum import Enum
from typing import Optional
import os
import sqlite3
from pathlib import Path

# Путь к БД
DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"


class Role(str, Enum):
    """Роли пользователей"""

    USER = "user"
    MANAGER = "manager"
    ADMIN = "admin"

    @classmethod
    def from_string(cls, value: str) -> "Role":
        """Преобразовать строку в Role с валидацией"""
        try:
            return cls(value.lower())
        except ValueError:
            # По умолчанию обычный пользователь
            return cls.USER


# Константы для быстрого доступа
ROLE_USER = Role.USER
ROLE_MANAGER = Role.MANAGER
ROLE_ADMIN = Role.ADMIN

# Администратор из .env
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))


def get_user_role(telegram_id: int) -> Role:
    """
    Получить роль пользователя по telegram_id

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        Role пользователя
    """
    if telegram_id == ADMIN_ID:
        # Админ всегда имеет роль admin, даже если не в БД
        return Role.ADMIN

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT role FROM users WHERE telegram_id = ?
            """,
            (telegram_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if result and result["role"]:
            return Role.from_string(result["role"])

        # Если роли нет в БД (старые пользователи)
        return Role.USER

    except sqlite3.Error:
        # При ошибке БД - обычный пользователь
        return Role.USER


def is_admin(telegram_id: int) -> bool:
    """
    Проверить является ли пользователь администратором

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        True если пользователь админ
    """
    return get_user_role(telegram_id) == Role.ADMIN


def is_manager(telegram_id: int) -> bool:
    """
    Проверить является ли пользователь менеджером или администратором

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        True если пользователь менеджер или админ
    """
    role = get_user_role(telegram_id)
    return role in (Role.MANAGER, Role.ADMIN)


def can_invite_users(telegram_id: int) -> bool:
    """
    Проверить может ли пользователь приглашать других

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        True если пользователь может приглашать (manager/admin)
    """
    return is_manager(telegram_id)


def set_user_role(telegram_id: int, role: Role) -> bool:
    """
    Установить роль пользователю

    Args:
        telegram_id: Telegram ID пользователя
        role: Новая роль

    Returns:
        True если успешно, иначе False
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users SET role = ? WHERE telegram_id = ?
            """,
            (role.value, telegram_id),
        )

        conn.commit()
        conn.close()

        return True

    except sqlite3.Error:
        return False


def get_role_display_name(role: Role) -> str:
    """
    Получить отображаемое имя роли для UI

    Args:
        role: Роль

    Returns:
        Отображаемое имя на русском
    """
    display_names = {
        Role.USER: "Пользователь",
        Role.MANAGER: "Менеджер",
        Role.ADMIN: "Администратор",
    }
    return display_names.get(role, "Пользователь")


def get_users_by_role(role, limit: int = 100) -> list[dict]:
    """
    Получить список пользователей определенной роли

    Args:
        role: Роль для фильтрации (Role или строка)
        limit: Максимальное количество пользователей

    Returns:
        Список пользователей с их данными
    """
    # Нормализация role в строку
    role_value = role.value if isinstance(role, Role) else str(role)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id, telegram_id, telegram_username, telegram_first_name,
                role, user_type, is_active, is_blocked,
                data_limit_bytes, used_bytes, expires_at,
                created_at
            FROM users
            WHERE role = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (role_value, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    except sqlite3.Error:
        return []


def migrate_admin_to_role():
    """
    Миграция: установить роль admin для TELEGRAM_ADMIN_ID

    Должна быть выполнена один раз после применения миграции БД
    """
    if ADMIN_ID == 0:
        print("Ошибка: TELEGRAM_ADMIN_ID не установлен в .env")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Проверить есть ли админ в БД
        cursor.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (ADMIN_ID,),
        )
        admin_exists = cursor.fetchone()

        if admin_exists:
            # Установить роль admin
            cursor.execute(
                "UPDATE users SET role = ? WHERE telegram_id = ?",
                (Role.ADMIN.value, ADMIN_ID),
            )
            print(f"Роль {Role.ADMIN.value} установлена для telegram_id={ADMIN_ID}")
        else:
            print(f"Предупреждение: Пользователь с telegram_id={ADMIN_ID} не найден в БД")
            print("Админ должен быть создан через /start")

        conn.commit()
        conn.close()

        return True

    except sqlite3.Error as e:
        print(f"Ошибка миграции: {e}")
        return False


if __name__ == "__main__":
    # Тестирование модуля
    print(f"ADMIN_ID из .env: {ADMIN_ID}")
    print(f"\nРоли:")
    for role in Role:
        print(f"  - {role.value}: {get_role_display_name(role)}")

    print(f"\nМиграция админа:")
    migrate_admin_to_role()
