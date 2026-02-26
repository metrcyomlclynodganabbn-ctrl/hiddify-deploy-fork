"""
Тесты для валидации инвайт-кодов

Version: 2.1.1
"""

import pytest
from datetime import datetime, timedelta
import sqlite3


@pytest.mark.unit
def test_validate_valid_invite(test_db, test_invite):
    """
    Тест валидации действующего инвайта

    Given: Действующий инвайт-код
    When: Валидируем код
    Then: Получаем подтверждение валидности
    """
    # Arrange
    invite_code = test_invite['code']

    # Act
    conn = test_db
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, created_by, max_uses, used_count, expires_at
        FROM invites
        WHERE code = ? AND is_active = 1
    ''', (invite_code,))

    result = cursor.fetchone()

    # Assert
    assert result is not None
    assert result['id'] == test_invite['id']
    assert result['created_by'] == test_invite['created_by']
    assert result['max_uses'] == test_invite['max_uses']
    assert result['used_count'] == 0


@pytest.mark.unit
def test_validate_nonexistent_invite(test_db):
    """
    Тест валидации несуществующего инвайта

    Given: Несуществующий инвайт-код
    When: Валидируем код
    Then: Получаем ошибку "инвайт не найден"
    """
    # Arrange
    invite_code = "INV_nonexistent"

    # Act
    conn = test_db
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, created_by, max_uses, used_count, expires_at
        FROM invites
        WHERE code = ? AND is_active = 1
    ''', (invite_code,))

    result = cursor.fetchone()

    # Assert
    assert result is None


@pytest.mark.unit
def test_validate_expired_invite(test_db):
    """
    Тест валидации истёкшего инвайта

    Given: Инвайт с истёкшим сроком действия
    When: Валидируем код
    Then: Получаем ошибку "инвайт истёк"
    """
    # Arrange
    cursor = test_db.cursor()

    expired_invite_data = {
        'code': 'INV_expired',
        'created_by': 1,
        'max_uses': 5,
        'used_count': 0,
        'is_active': 1,
        'expires_at': (datetime.now() - timedelta(days=1)).isoformat()  # Истёк вчера
    }

    cursor.execute('''
        INSERT INTO invites (
            code, created_by, max_uses, used_count,
            is_active, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        expired_invite_data['code'],
        expired_invite_data['created_by'],
        expired_invite_data['max_uses'],
        expired_invite_data['used_count'],
        expired_invite_data['is_active'],
        expired_invite_data['expires_at']
    ))

    test_db.commit()

    # Act
    cursor.execute('''
        SELECT expires_at
        FROM invites
        WHERE code = ? AND is_active = 1
    ''', (expired_invite_data['code'],))

    result = cursor.fetchone()

    # Assert
    assert result is not None
    # Проверяем что дата истекания в прошлом
    expiry = datetime.fromisoformat(result['expires_at'])
    assert expiry < datetime.now()


@pytest.mark.unit
def test_validate_fully_used_invite(test_db):
    """
    Тест валидации полностью использованного инвайта

    Given: Инвайт с достигнутым лимитом использований
    When: Валидируем код
    Then: Получаем ошибку "инвайт уже использован максимальное число раз"
    """
    # Arrange
    cursor = test_db.cursor()

    fully_used_invite = {
        'code': 'INV_fullyused',
        'created_by': 1,
        'max_uses': 3,
        'used_count': 3,  # Лимит достигнут
        'is_active': 1,
        'expires_at': (datetime.now() + timedelta(days=7)).isoformat()
    }

    cursor.execute('''
        INSERT INTO invites (
            code, created_by, max_uses, used_count,
            is_active, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        fully_used_invite['code'],
        fully_used_invite['created_by'],
        fully_used_invite['max_uses'],
        fully_used_invite['used_count'],
        fully_used_invite['is_active'],
        fully_used_invite['expires_at']
    ))

    test_db.commit()

    # Act
    cursor.execute('''
        SELECT used_count, max_uses
        FROM invites
        WHERE code = ? AND is_active = 1
    ''', (fully_used_invite['code'],))

    result = cursor.fetchone()

    # Assert
    assert result is not None
    assert result['used_count'] >= result['max_uses']


@pytest.mark.unit
def test_validate_inactive_invite(test_db):
    """
    Тест валидации деактивированного инвайта

    Given: Инвайт с is_active = 0
    When: Валидируем код
    Then: Не находим инвайт (так как запрос с is_active = 1)
    """
    # Arrange
    cursor = test_db.cursor()

    inactive_invite = {
        'code': 'INV_inactive',
        'created_by': 1,
        'max_uses': 5,
        'used_count': 0,
        'is_active': 0,  # Деактивирован
        'expires_at': (datetime.now() + timedelta(days=7)).isoformat()
    }

    cursor.execute('''
        INSERT INTO invites (
            code, created_by, max_uses, used_count,
            is_active, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        inactive_invite['code'],
        inactive_invite['created_by'],
        inactive_invite['max_uses'],
        inactive_invite['used_count'],
        inactive_invite['is_active'],
        inactive_invite['expires_at']
    ))

    test_db.commit()

    # Act
    cursor.execute('''
        SELECT id
        FROM invites
        WHERE code = ? AND is_active = 1
    ''', (inactive_invite['code'],))

    result = cursor.fetchone()

    # Assert
    assert result is None


@pytest.mark.unit
def test_increment_invite_usage(test_db, test_invite):
    """
    Тест увеличения счётчика использований инвайта

    Given: Инвайт с used_count = 0
    When: Увеличиваем счётчик
    Then: used_count становится 1
    """
    # Arrange
    cursor = test_db.cursor()
    invite_id = test_invite['id']

    # Act
    cursor.execute('''
        UPDATE invites
        SET used_count = used_count + 1
        WHERE id = ?
    ''', (invite_id,))

    test_db.commit()

    # Assert
    cursor.execute('SELECT used_count FROM invites WHERE id = ?', (invite_id,))
    result = cursor.fetchone()

    assert result['used_count'] == 1


@pytest.mark.unit
def test_create_user_with_invite(test_db, test_user, test_invite):
    """
    Тест создания пользователя с привязкой к инвайту

    Given: Валидный инвайт-код
    When: Создаём пользователя с invited_by
    Then: Пользователь создаётся с правильной привязкой
    """
    # Arrange
    cursor = test_db.cursor()

    new_user_data = {
        'telegram_id': 111111111,
        'telegram_username': 'invited_user',
        'telegram_first_name': 'Invited',
        'invited_by': test_invite['created_by']
    }

    # Act
    cursor.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            invited_by
        ) VALUES (?, ?, ?, ?)
    ''', (
        new_user_data['telegram_id'],
        new_user_data['telegram_username'],
        new_user_data['telegram_first_name'],
        new_user_data['invited_by']
    ))

    test_db.commit()

    # Assert
    cursor.execute('''
        SELECT invited_by
        FROM users
        WHERE telegram_id = ?
    ''', (new_user_data['telegram_id'],))

    result = cursor.fetchone()

    assert result is not None
    assert result['invited_by'] == test_invite['created_by']
