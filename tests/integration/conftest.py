"""
Фикстуры для интеграционных тестов

Используются для настройки тестового окружения
"""

import os
import sys
import sqlite3
import tempfile
import pytest
from pathlib import Path

# Добавить scripts в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


@pytest.fixture(scope="function")
def temp_db_path():
    """Создать временную базу данных для тестов"""

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="function")
def db_connection(temp_db_path):
    """Создать подключение к временной БД"""

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row

    yield conn

    conn.close()


@pytest.fixture(scope="function")
def test_env_vars(temp_db_path, monkeypatch):
    """Установить тестовые переменные окружения"""

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_12345")
    monkeypatch.setenv("TELEGRAM_ADMIN_ID", "123456789")
    monkeypatch.setenv("PANEL_DOMAIN", "test.example.com")
    monkeypatch.setenv("HIDDIFY_API_TOKEN", "test_api_token")
    monkeypatch.setenv("VPS_IP", "1.2.3.4")
    monkeypatch.setenv("REALITY_PUBLIC_KEY", "test_public_key")
    monkeypatch.setenv("REALITY_SNI", "www.apple.com")

    # Переопределить путь к БД
    # В реальном коде нужно, чтобы monitor_bot использовал переменную окружения

    return {
        "TELEGRAM_BOT_TOKEN": "test_token_12345",
        "TELEGRAM_ADMIN_ID": "123456789",
        "DB_PATH": temp_db_path,
    }


@pytest.fixture(scope="function")
def init_test_db(db_connection, temp_db_path):
    """Инициализировать тестовую БД схемой с WAL mode"""

    # Включить WAL mode для конкурентного доступа
    db_connection.execute('PRAGMA journal_mode=WAL')
    db_connection.execute('PRAGMA busy_timeout=30000')
    db_connection.execute('PRAGMA foreign_keys=ON')

    # Таблица пользователей
    db_connection.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            telegram_username VARCHAR(255),
            telegram_first_name VARCHAR(255),
            user_type VARCHAR(20) DEFAULT 'private',
            invite_code VARCHAR(50) UNIQUE,
            invited_by INTEGER,
            data_limit_bytes BIGINT DEFAULT 104857600000,
            expire_days INTEGER DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            used_bytes BIGINT DEFAULT 0,
            last_connection TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            is_blocked BOOLEAN DEFAULT 0,
            vless_enabled BOOLEAN DEFAULT 1,
            hysteria2_enabled BOOLEAN DEFAULT 1,
            ss2022_enabled BOOLEAN DEFAULT 1,
            vless_uuid VARCHAR(36),
            hysteria2_password VARCHAR(255),
            ss2022_password VARCHAR(255),
            role VARCHAR(20) DEFAULT 'user'
        )
    ''')

    # Таблица инвайтов
    db_connection.execute('''
        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(50) UNIQUE NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    db_connection.commit()

    return db_connection


@pytest.fixture(scope="function")
def test_db_with_path(temp_db_path, init_test_db):
    """Фикстура для тестов hiddify_api - возвращает и путь, и connection"""
    return {
        'path': temp_db_path,
        'conn': init_test_db
    }


@pytest.fixture(scope="function")
def test_user_data():
    """Данные тестового пользователя"""

    return {
        "telegram_id": 123456789,
        "telegram_username": "@testuser",
        "telegram_first_name": "Test",
        "user_type": "private",
        "data_limit_bytes": 104857600000,  # 100 GB
        "expire_days": 30,
        "is_active": True,
        "is_blocked": False,
    }


@pytest.fixture(scope="function")
def test_invite_data():
    """Данные тестового инвайта"""

    return {
        "code": "INV_TEST123456",
        "max_uses": 1,
        "used_count": 0,
        "is_active": True,
    }
