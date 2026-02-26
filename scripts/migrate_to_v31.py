#!/usr/bin/env python3
"""
Скрипт применения миграции v3.1: Система ролей

Выполняет:
1. Применяет SQL миграцию
2. Обновляет роль админа
3. Проверяет результат

Использование:
    python scripts/migrate_to_v31.py

Дата: 2026-02-26
"""

import os
import sys
import sqlite3
from pathlib import Path

# Добавляем родительскую директорию в path
sys.path.insert(0, str(Path(__file__).parent))

# Константы
DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"
MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "v3.1_add_roles.sql"


def apply_migration():
    """Применить SQL миграцию"""

    if not MIGRATION_FILE.exists():
        print(f"❌ Файл миграции не найден: {MIGRATION_FILE}")
        return False

    print(f"📄 Читаю миграцию из: {MIGRATION_FILE}")

    with open(MIGRATION_FILE, 'r') as f:
        migration_sql = f.read()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Применить миграцию по частям (разделенную по ;)
        statements = [s.strip() for s in migration_sql.split(';') if s.strip()]

        for statement in statements:
            if statement and not statement.startswith('--'):
                print(f"Выполняю: {statement[:50]}...")
                cursor.execute(statement)

        conn.commit()
        conn.close()

        print("✅ Миграция применена успешно")
        return True

    except sqlite3.Error as e:
        print(f"❌ Ошибка применения миграции: {e}")
        return False


def update_admin_role():
    """Обновить роль для админа"""

    ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

    if not ADMIN_ID:
        print("❌ TELEGRAM_ADMIN_ID не найден в .env")
        return False

    try:
        from roles import Role, set_user_role, migrate_admin_to_role

        print(f"🔑 Обновляю роль для telegram_id={ADMIN_ID}")

        # Используем функцию из roles.py
        result = migrate_admin_to_role()

        if result:
            print("✅ Роль админа обновлена")
        else:
            print("⚠️  Роль админа не обновлена (пользователь не найден в БД?)")

        return result

    except ImportError as e:
        print(f"❌ Модуль roles не найден: {e}")
        return False


def verify_migration():
    """Проверить результат миграции"""

    try:
        from roles import Role, get_users_by_role

        print("\n📊 Статистика ролей:")

        for role in [Role.USER, Role.MANAGER, Role.ADMIN]:
            users = get_users_by_role(role, limit=1000)
            print(f"  {get_role_display_name(role)}: {len(users)} пользователей")

        # Проверить что колонка role существует
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()

        if "role" in columns:
            print("✅ Колонка 'role' существует в таблице users")
            return True
        else:
            print("❌ Колонка 'role' НЕ найдена в таблице users")
            return False

    except ImportError:
        print("⚠️  Модуль roles не найден, проверка через SQL")

        # Fallback проверка через SQL
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        if "role" in columns:
            print("✅ Колонка 'role' существует в таблице users")

            # Показать статистику по ролям
            cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
            results = cursor.fetchall()
            print("\n📊 Статистика ролей:")
            for role, count in results:
                print(f"  {role}: {count} пользователей")

            conn.close()
            return True
        else:
            print("❌ Колонка 'role' НЕ найдена")
            conn.close()
            return False


def get_role_display_name(role_str):
    """Получить отображаемое имя роли (fallback)"""
    display_names = {
        "user": "Пользователь",
        "manager": "Менеджер",
        "admin": "Администратор",
    }
    return display_names.get(role_str, "Пользователь")


def main():
    """Главная функция"""

    print("=== Миграция v3.1: Система ролей ===\n")

    # Проверка БД
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        print("💡 Сначала запустите бота для создания БД")
        return 1

    # 1. Применить миграцию
    print("Шаг 1: Применение SQL миграции")
    if not apply_migration():
        return 1

    # 2. Обновить роль админа
    print("\nШаг 2: Обновление роли админа")
    if not update_admin_role():
        print("⚠️  Предупреждение: Роль админа не обновлена")

    # 3. Проверить результат
    print("\nШаг 3: Проверка результата")
    if verify_migration():
        print("\n🎉 Миграция v3.1 завершена успешно!")
        print("\n💡 Следующие шаги:")
        print("   1. Перезапустите бота: systemctl restart hiddify-bot")
        print("   2. Протестируйте систему ролей")
        print("   3. Запустите тесты: pytest tests/test_roles.py -v")
        return 0
    else:
        print("\n❌ Миграция завершилась с ошибками")
        return 1


if __name__ == "__main__":
    sys.exit(main())
