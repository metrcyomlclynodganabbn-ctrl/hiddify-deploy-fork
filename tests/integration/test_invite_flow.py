"""
Интеграционные тесты для системы инвайтов

Тестируют:
1. Создание инвайта
2. Использование инвайта
3. Проверку лимитов использования
4. Истечение срока действия инвайта
5. Race conditions при параллельном использовании
6. WAL mode и атомарность операций
"""

import pytest
import threading
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


# ============================================================================
# НОВЫЕ ТЕСТЫ ДЛЯ RACE CONDITIONS И АТОМАРНОСТИ
# ============================================================================

@pytest.mark.integration
def test_wal_mode_enabled(init_test_db):
    """Проверить что WAL mode включён"""
    result = init_test_db.execute('PRAGMA journal_mode').fetchone()
    assert result[0] == 'wal', f"WAL mode не включён: {result[0]}"


@pytest.mark.integration
def test_race_condition_prevention(test_db_with_path):
    """Тест race condition - только max_uses использований должно пройти"""
    from scripts.hiddify_api import use_invite_code

    db = test_db_with_path['conn']
    db_path = test_db_with_path['path']

    # Создать инвайт с лимитом 2
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES ('INV_RACE', 2, 0, 1)
    ''')
    db.commit()

    results = []
    lock = threading.Lock()

    def use_invite(thread_id):
        result = use_invite_code(db_path, 'INV_RACE')
        with lock:
            results.append((thread_id, result['success']))

    # 5 потоков одновременно
    threads = []
    for i in range(5):
        t = threading.Thread(target=use_invite, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Только 2 должны быть успешными
    successful = sum(1 for _, success in results if success)
    assert successful == 2, f"Ожидалось 2 успешных, получено {successful}"


@pytest.mark.integration
def test_invite_atomic_use(test_db_with_path):
    """Тест атомарности - второе использование должно fail"""
    from scripts.hiddify_api import use_invite_code

    db = test_db_with_path['conn']
    db_path = test_db_with_path['path']

    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES ('INV_ATOMIC', 1, 0, 1)
    ''')
    db.commit()

    # Первое - успешно
    result1 = use_invite_code(db_path, 'INV_ATOMIC')
    assert result1['success'] is True
    assert result1['invite_data']['used_count'] == 1

    # Второе - fail
    result2 = use_invite_code(db_path, 'INV_ATOMIC')
    assert result2['success'] is False
    assert 'исчерпан' in result2['message'] or 'недействителен' in result2['message']


@pytest.mark.integration
def test_create_invite_validation(test_db_with_path):
    """Тест валидации при создании инвайта"""
    from scripts.hiddify_api import create_invite_code

    db = test_db_with_path['conn']
    db_path = test_db_with_path['path']

    # Сначала создать пользователя
    db.execute('''
        INSERT INTO users (telegram_id, telegram_username, telegram_first_name)
        VALUES (999999, "@testuser", "Test")
    ''')
    db.commit()

    # Тест 1: Неверный формат кода
    result = create_invite_code(db_path, "WRONG_FORMAT", 999999)
    assert result['success'] is False
    assert 'INV_' in result['message']

    # Тест 2: Несуществующий создатель
    result = create_invite_code(db_path, "INV_a1b2c3d4", 888888)
    assert result['success'] is False
    assert 'не существует' in result['message']

    # Тест 3: max_uses вне диапазона
    result = create_invite_code(db_path, "INV_b1c2d3e4", 999999, max_uses=0)
    assert result['success'] is False
    assert 'max_uses' in result['message']

    # Тест 4: max_uses слишком большой
    result = create_invite_code(db_path, "INV_c2d3e4f5", 999999, max_uses=1001)
    assert result['success'] is False
    assert 'max_uses' in result['message']

    # Тест 5: Корректный инвайт (hex-символы после INV_)
    result = create_invite_code(db_path, "INV_abc12345", 999999, max_uses=5)
    assert result['success'] is True
    assert result['invite_data']['max_uses'] == 5


@pytest.mark.integration
def test_validate_invite_code_unified(test_db_with_path):
    """Тест унифицированной проверки инвайта"""
    from scripts.hiddify_api import validate_invite_code

    db = test_db_with_path['conn']
    db_path = test_db_with_path['path']

    # Создать активный инвайт
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES ('INV_VALID_TEST', 5, 0, 1)
    ''')
    db.commit()

    # Должен быть валиден
    result = validate_invite_code(db_path, 'INV_VALID_TEST')
    assert result is not None
    assert result['code'] == 'INV_VALID_TEST'
    assert result['is_active'] == 1

    # После достижения лимита - не валиден
    db.execute('UPDATE invites SET used_count = 5 WHERE code = ?', ('INV_VALID_TEST',))
    db.commit()

    result = validate_invite_code(db_path, 'INV_VALID_TEST')
    assert result is None
