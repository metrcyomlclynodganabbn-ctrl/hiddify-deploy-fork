"""
Pytest configuration and fixtures for Hiddify Manager tests

Version: 2.1.1
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def test_db_path(tmp_path):
    """
    Создать временную БД для тестов

    Returns:
        str: Путь к временной базе данных
    """
    db_path = tmp_path / "test_bot.db"

    # Создать схему БД
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Таблица users
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            telegram_username TEXT,
            telegram_first_name TEXT,
            is_active INTEGER DEFAULT 1,
            is_blocked INTEGER DEFAULT 0,
            is_trial INTEGER DEFAULT 0,
            invited_by INTEGER,
            expires_at TEXT,
            data_limit_bytes INTEGER DEFAULT 107374182400,
            used_bytes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invited_by) REFERENCES users(id)
        )
    ''')

    # Таблица invites
    cursor.execute('''
        CREATE TABLE invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            created_by INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # Таблица connections
    cursor.execute('''
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            protocol TEXT,
            location_city TEXT,
            location_country TEXT,
            connected_at TEXT,
            disconnected_at TEXT,
            bytes_sent INTEGER DEFAULT 0,
            bytes_received INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

    return str(db_path)


@pytest.fixture
def test_db(test_db_path):
    """
    Создать подключение к тестовой БД

    Args:
        test_db_path: Фикстура пути к БД

    Returns:
        sqlite3.Connection: Подключение к БД
    """
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row

    yield conn

    conn.close()


@pytest.fixture
def test_user(test_db):
    """
    Создать тестового пользователя

    Args:
        test_db: Подключение к БД

    Returns:
        dict: Данные пользователя
    """
    cursor = test_db.cursor()

    user_data = {
        'telegram_id': 123456789,
        'telegram_username': 'testuser',
        'telegram_first_name': 'Test',
        'is_active': 1,
        'is_blocked': 0,
        'is_trial': 0,
        'expires_at': (datetime.now() + timedelta(days=30)).isoformat(),
        'data_limit_bytes': 100 * 1024**3,  # 100 GB
        'used_bytes': 0
    }

    cursor.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            is_active, is_blocked, is_trial, expires_at,
            data_limit_bytes, used_bytes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_data['telegram_id'],
        user_data['telegram_username'],
        user_data['telegram_first_name'],
        user_data['is_active'],
        user_data['is_blocked'],
        user_data['is_trial'],
        user_data['expires_at'],
        user_data['data_limit_bytes'],
        user_data['used_bytes']
    ))

    test_db.commit()

    user_data['id'] = cursor.lastrowid
    return user_data


@pytest.fixture
def test_admin(test_db):
    """
    Создать тестового администратора

    Args:
        test_db: Подключение к БД

    Returns:
        dict: Данные администратора
    """
    cursor = test_db.cursor()

    admin_data = {
        'telegram_id': 999999999,
        'telegram_username': 'admin',
        'telegram_first_name': 'Admin',
        'is_active': 1,
        'is_blocked': 0,
        'is_trial': 0,
        'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),
    }

    cursor.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            is_active, is_blocked, is_trial, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        admin_data['telegram_id'],
        admin_data['telegram_username'],
        admin_data['telegram_first_name'],
        admin_data['is_active'],
        admin_data['is_blocked'],
        admin_data['is_trial'],
        admin_data['expires_at']
    ))

    test_db.commit()

    admin_data['id'] = cursor.lastrowid
    return admin_data


@pytest.fixture
def test_invite(test_db, test_admin):
    """
    Создать тестовый инвайт

    Args:
        test_db: Подключение к БД
        test_admin: Данные администратора

    Returns:
        dict: Данные инвайта
    """
    cursor = test_db.cursor()

    invite_data = {
        'code': 'INV_test123456',
        'created_by': test_admin['id'],
        'max_uses': 5,
        'used_count': 0,
        'is_active': 1,
        'expires_at': (datetime.now() + timedelta(days=7)).isoformat()
    }

    cursor.execute('''
        INSERT INTO invites (
            code, created_by, max_uses, used_count,
            is_active, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        invite_data['code'],
        invite_data['created_by'],
        invite_data['max_uses'],
        invite_data['used_count'],
        invite_data['is_active'],
        invite_data['expires_at']
    ))

    test_db.commit()

    invite_data['id'] = cursor.lastrowid
    return invite_data


@pytest.fixture
def mock_bot():
    """
    Создать мок Telegram бота

    Returns:
        Mock: Мок объекта бота
    """
    bot = Mock()

    # Мок для send_message
    bot.send_message = Mock(return_value=Mock(message_id=1))

    # Мок для send_photo
    bot.send_photo = Mock(return_value=Mock(message_id=1))

    # Мок для edit_message_text
    bot.edit_message_text = Mock(return_value=True)

    # Мок для answer_callback_query
    bot.answer_callback_query = Mock(return_value=True)

    return bot


@pytest.fixture
def mock_message():
    """
    Создать мок Telegram сообщения

    Returns:
        Mock: Мок объекта сообщения
    """
    message = Mock()
    message.chat.id = 123456789
    message.message_id = 1
    message.text = "/start"
    message.from_user.id = 123456789
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"

    return message


@pytest.fixture
def mock_callback():
    """
    Создать мок callback query

    Returns:
        Mock: Мок объекта callback
    """
    callback = Mock()
    callback.id = "test_callback_123"
    callback.data = "test_data"
    callback.message.chat.id = 123456789
    callback.message.message_id = 1

    return callback


# ═══════════════════════════════════════════════════════════════
# PYTEST CONFIGURATION
# ═══════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Настройка pytest"""
    config.addinivalue_line(
        "markers", "integration: маркер для интеграционных тестов"
    )
    config.addinivalue_line(
        "markers", "unit: маркер для unit тестов"
    )
    config.addinivalue_line(
        "markers", "slow: маркер для медленных тестов"
    )


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    Установить тестовые переменные окружения для всех тестов
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123")
    monkeypatch.setenv("TELEGRAM_ADMIN_ID", "999999999")
    monkeypatch.setenv("DB_PATH", "/tmp/test_bot.db")
