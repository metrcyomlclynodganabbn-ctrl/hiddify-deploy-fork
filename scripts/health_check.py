#!/usr/bin/env python3
"""
Health check для бота и базы данных

Проверяет:
1. Подключение к базе данных
2. Наличие необходимых таблиц
3. Работоспособность бота (если запущен)
4. Hiddify API (если доступен)
"""

import os
import sys
import sqlite3
import requests
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), '../data/bot.db'))
PANEL_DOMAIN = os.getenv('PANEL_DOMAIN', '')
HIDDIFY_API_TOKEN = os.getenv('HIDDIFY_API_TOKEN', '')


class Colors:
    """Цвета для вывода в консоль"""

    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_success(message):
    """Вывести успешное сообщение"""
    print(f"{Colors.GREEN}✓{Colors.NC} {message}")


def print_error(message):
    """Вывести ошибку"""
    print(f"{Colors.RED}✗{Colors.NC} {message}")


def print_warning(message):
    """Вывести предупреждение"""
    print(f"{Colors.YELLOW}⚠{Colors.NC} {message}")


def print_info(message):
    """Вывести информационное сообщение"""
    print(f"{Colors.BLUE}ℹ{Colors.NC} {message}")


def check_database():
    """Проверить подключение к базе данных"""

    print_info("Проверка базы данных...")

    try:
        # Проверить существование файла БД
        db_path = Path(DB_PATH)
        if not db_path.exists():
            print_error(f"Файл базы данных не найден: {DB_PATH}")
            return False

        print_success(f"Файл базы данных найден: {DB_PATH}")

        # Подключиться к БД
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Проверить наличие таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {'users', 'invites', 'connections'}
        missing_tables = required_tables - tables

        if missing_tables:
            print_error(f"Отсутствуют таблицы: {', '.join(missing_tables)}")
            conn.close()
            return False

        print_success(f"Все необходимые таблицы существуют: {', '.join(required_tables)}")

        # Проверить количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print_success(f"Пользователей в БД: {user_count}")

        # Проверить количество инвайтов
        cursor.execute("SELECT COUNT(*) FROM invites")
        invite_count = cursor.fetchone()[0]
        print_success(f"Инвайтов в БД: {invite_count}")

        conn.close()
        return True

    except sqlite3.Error as e:
        print_error(f"Ошибка базы данных: {e}")
        return False


def check_bot_process():
    """Проверить что бот работает"""

    print_info("Проверка процесса бота...")

    try:
        # Проверить процесс с помощью ps
        import psutil

        found = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'python' in cmdline[0].lower():
                    if any('monitor_bot.py' in arg for arg in cmdline):
                        found = True
                        print_success(f"Бот работает (PID: {proc.info['pid']})")
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not found:
            print_warning("Процесс бота не найден")

        return found

    except ImportError:
        print_warning("psutil не установлен, пропускаю проверку процесса")
        return True
    except Exception as e:
        print_warning(f"Ошибка при проверке процесса: {e}")
        return True


def check_hiddify_api():
    """Проверить Hiddify API"""

    print_info("Проверка Hiddify API...")

    if not PANEL_DOMAIN:
        print_warning("PANEL_DOMAIN не установлен, пропускаю проверку API")
        return True

    try:
        # Проверить доступность панели
        url = f"https://{PANEL_DOMAIN}/api/v1/"
        headers = {}

        if HIDDIFY_API_TOKEN:
            headers['Authorization'] = f'Bearer {HIDDIFY_API_TOKEN}'

        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code in [200, 401]:  # 401 значит API доступен, но токен неверный
            print_success(f"Hiddify API доступен (статус: {response.status_code})")
            return True
        else:
            print_warning(f"Hiddify API вернул статус: {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        print_warning("Hiddify API не ответил (timeout)")
        return False
    except requests.exceptions.ConnectionError:
        print_warning("Hiddify API недоступен (connection error)")
        return False
    except Exception as e:
        print_warning(f"Ошибка при проверке API: {e}")
        return False


def check_environment():
    """Проверить переменные окружения"""

    print_info("Проверка переменных окружения...")

    required_vars = ['TELEGRAM_BOT_TOKEN']
    optional_vars = ['TELEGRAM_ADMIN_ID', 'PANEL_DOMAIN', 'HIDDIFY_API_TOKEN']

    all_ok = True

    for var in required_vars:
        if os.getenv(var):
            print_success(f"{var} установлен")
        else:
            print_error(f"{var} НЕ установлен")
            all_ok = False

    for var in optional_vars:
        if os.getenv(var):
            print_success(f"{var} установлен")
        else:
            print_warning(f"{var} не установлен (опционально)")

    return all_ok


def main():
    """Главная функция"""

    print(f"\n{Colors.BLUE}=== Hiddify Manager Health Check ==={Colors.NC}\n")

    checks = [
        ("Переменные окружения", check_environment),
        ("База данных", check_database),
        ("Процесс бота", check_bot_process),
        ("Hiddify API", check_hiddify_api),
    ]

    results = []

    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
            print()
        except Exception as e:
            print_error(f"Критическая ошибка при проверке '{name}': {e}")
            results.append((name, False))
            print()

    # Итог
    print(f"{Colors.BLUE}=== Результаты ==={Colors.NC}")

    all_ok = True
    for name, result in results:
        if result:
            print_success(f"{name}: OK")
        else:
            print_error(f"{name}: FAILED")
            all_ok = False

    print()

    if all_ok:
        print_success("Все проверки пройдены!")
        return 0
    else:
        print_error("Некоторые проверки не пройдены")
        return 1


if __name__ == '__main__':
    sys.exit(main())
