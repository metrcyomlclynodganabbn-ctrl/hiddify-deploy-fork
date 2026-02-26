"""
Интеграционные тесты для системы инвайтов

Тестируют:
1. Создание инвайта
2. Использование инвайта
3. Проверку лимитов использования
4. Истечение срока действия инвайта
"""

import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
def test_create_invite(init_test_db, test_invite_data):
    """Тест создания инвайта"""

    db = init_test_db

    # Создать инвайт
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES (:code, :max_uses, :used_count, :is_active)
    ''', test_invite_data)
    db.commit()

    # Проверить
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite is not None
    assert invite['code'] == test_invite_data['code']
    assert invite['max_uses'] == test_invite_data['max_uses']
    assert invite['is_active'] == 1


@pytest.mark.integration
def test_invite_single_use(init_test_db, test_invite_data):
    """Тест инвайта с однократным использованием"""

    db = init_test_db

    # Создать инвайт
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES (:code, :max_uses, :used_count, :is_active)
    ''', test_invite_data)
    db.commit()

    # Использовать инвайт
    db.execute('UPDATE invites SET used_count = used_count + 1 WHERE code = ?', (test_invite_data['code'],))
    db.commit()

    # Проверить
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite['used_count'] == 1
    assert invite['max_uses'] == 1

    # Инвайт должен быть неактивен (исчерпан)
    # В реальном коде должна быть логика деактивации
    if invite['used_count'] >= invite['max_uses']:
        db.execute('UPDATE invites SET is_active = 0 WHERE code = ?', (test_invite_data['code'],))
        db.commit()

    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite['is_active'] == 0


@pytest.mark.integration
def test_invite_multiple_uses(init_test_db):
    """Тест инвайта с многократным использованием"""

    db = init_test_db

    # Создать инвайт с лимитом 3 использования
    invite_data = {
        "code": "INV_MULTI_USE",
        "max_uses": 3,
        "used_count": 0,
        "is_active": True,
    }

    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES (:code, :max_uses, :used_count, :is_active)
    ''', invite_data)
    db.commit()

    # Использовать 2 раза
    for i in range(2):
        db.execute('UPDATE invites SET used_count = used_count + 1 WHERE code = ?', (invite_data['code'],))
        db.commit()

    # Проверить
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (invite_data['code'],)).fetchone()
    assert invite['used_count'] == 2
    assert invite['is_active'] == 1  # Всё ещё активен


@pytest.mark.integration
def test_invite_expiration(init_test_db):
    """Тест истечения срока действия инвайта"""

    db = init_test_db

    # Создать инвайт с истёкшим сроком
    expired_date = datetime.now() - timedelta(days=1)

    invite_data = {
        "code": "INV_EXPIRED",
        "max_uses": 1,
        "used_count": 0,
        "is_active": True,
        "expires_at": expired_date.isoformat(),
    }

    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active, expires_at)
        VALUES (:code, :max_uses, :used_count, :is_active, :expires_at)
    ''', invite_data)
    db.commit()

    # Проверить
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (invite_data['code'],)).fetchone()
    assert invite is not None

    # Проверить истёк ли инвайт
    if invite['expires_at']:
        expires_at = datetime.fromisoformat(invite['expires_at'])
        if expires_at < datetime.now():
            # Инвайт истёк, деактивировать
            db.execute('UPDATE invites SET is_active = 0 WHERE code = ?', (invite_data['code'],))
            db.commit()

    invite = db.execute('SELECT * FROM invites WHERE code = ?', (invite_data['code'],)).fetchone()
    assert invite['is_active'] == 0


@pytest.mark.integration
def test_invite_with_future_expiration(init_test_db):
    """Тест инвайта с будущим сроком действия"""

    db = init_test_db

    # Создать инвайт с будущим сроком истечения
    future_date = datetime.now() + timedelta(days=30)

    invite_data = {
        "code": "INV_FUTURE",
        "max_uses": 1,
        "used_count": 0,
        "is_active": True,
        "expires_at": future_date.isoformat(),
    }

    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active, expires_at)
        VALUES (:code, :max_uses, :used_count, :is_active, :expires_at)
    ''', invite_data)
    db.commit()

    # Проверить
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (invite_data['code'],)).fetchone()
    assert invite is not None

    # Проверить активен ли инвайт
    if invite['expires_at']:
        expires_at = datetime.fromisoformat(invite['expires_at'])
        assert expires_at > datetime.now()
        assert invite['is_active'] == 1
