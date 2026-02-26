"""
Интеграционные тесты для работы с базой данных

Тестируют:
1. CRUD операции с пользователями
2. CRUD операции с инвайтами
3. Связи между таблицами
"""

import pytest


@pytest.mark.integration
def test_create_user(init_test_db, test_user_data):
    """Тест создания пользователя"""

    db = init_test_db

    # Создать пользователя
    user_data = test_user_data.copy()
    user_data['vless_uuid'] = 'test-uuid-12345'
    user_data['hysteria2_password'] = 'test-hysteria-password'
    user_data['ss2022_password'] = 'test-ss2022-password'

    db.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            vless_uuid, hysteria2_password, ss2022_password
        ) VALUES (
            :telegram_id, :telegram_username, :telegram_first_name,
            :vless_uuid, :hysteria2_password, :ss2022_password
        )
    ''', user_data)
    db.commit()

    # Проверить
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user is not None
    assert user['telegram_username'] == test_user_data['telegram_username']


@pytest.mark.integration
def test_create_and_get_invite(init_test_db, test_invite_data):
    """Тест создания и получения инвайта"""

    db = init_test_db

    # Создать инвайт
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES (:code, :max_uses, :used_count, :is_active)
    ''', test_invite_data)
    db.commit()

    # Получить инвайт
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite is not None
    assert invite['code'] == test_invite_data['code']
    assert invite['max_uses'] == test_invite_data['max_uses']
    assert invite['is_active'] == 1


@pytest.mark.integration
def test_invite_usage_tracking(init_test_db, test_invite_data, test_user_data):
    """Тест отслеживания использования инвайта"""

    db = init_test_db

    # Создать инвайт
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES (:code, :max_uses, :used_count, :is_active)
    ''', test_invite_data)
    db.commit()

    # Создать пользователя с инвайтом
    user_data = test_user_data.copy()
    user_data['vless_uuid'] = 'test-uuid-12345'
    user_data['hysteria2_password'] = 'test-hysteria-password'
    user_data['ss2022_password'] = 'test-ss2022-password'
    user_data['invite_code'] = test_invite_data['code']

    db.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            invite_code, vless_uuid, hysteria2_password, ss2022_password
        ) VALUES (
            :telegram_id, :telegram_username, :telegram_first_name,
            :invite_code, :vless_uuid, :hysteria2_password, :ss2022_password
        )
    ''', user_data)
    db.commit()

    # Увеличить счётчик использования
    db.execute('UPDATE invites SET used_count = used_count + 1 WHERE code = ?', (test_invite_data['code'],))
    db.commit()

    # Проверить
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite['used_count'] == 1


@pytest.mark.integration
def test_user_soft_delete(init_test_db, test_user_data):
    """Тест мягкого удаления пользователя"""

    db = init_test_db

    # Создать пользователя
    user_data = test_user_data.copy()
    user_data['vless_uuid'] = 'test-uuid-12345'
    user_data['hysteria2_password'] = 'test-hysteria-password'
    user_data['ss2022_password'] = 'test-ss2022-password'

    db.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            vless_uuid, hysteria2_password, ss2022_password
        ) VALUES (
            :telegram_id, :telegram_username, :telegram_first_name,
            :vless_uuid, :hysteria2_password, :ss2022_password
        )
    ''', user_data)
    db.commit()

    # Мягкое удаление
    db.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (user_data['telegram_id'],))
    db.commit()

    # Проверить что пользователь деактивирован
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user['is_active'] == 0

    # Проверить что запись ещё существует (не физически удалена)
    assert user is not None


@pytest.mark.integration
def test_unique_telegram_id_constraint(init_test_db, test_user_data):
    """Тест ограничения уникальности telegram_id"""

    db = init_test_db

    # Создать пользователя
    user_data = test_user_data.copy()
    user_data['vless_uuid'] = 'test-uuid-12345'
    user_data['hysteria2_password'] = 'test-hysteria-password'
    user_data['ss2022_password'] = 'test-ss2022-password'

    db.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            vless_uuid, hysteria2_password, ss2022_password
        ) VALUES (
            :telegram_id, :telegram_username, :telegram_first_name,
            :vless_uuid, :hysteria2_password, :ss2022_password
        )
    ''', user_data)
    db.commit()

    # Попытка создать пользователя с тем же telegram_id
    with pytest.raises(sqlite3.IntegrityError):
        user_data2 = test_user_data.copy()
        user_data2['telegram_id'] = test_user_data['telegram_id']  # Такой же
        user_data2['telegram_username'] = '@anotheruser'
        user_data2['vless_uuid'] = 'test-uuid-67890'
        user_data2['hysteria2_password'] = 'test-hysteria-password-2'
        user_data2['ss2022_password'] = 'test-ss2022-password-2'

        db.execute('''
            INSERT INTO users (
                telegram_id, telegram_username, telegram_first_name,
                vless_uuid, hysteria2_password, ss2022_password
            ) VALUES (
                :telegram_id, :telegram_username, :telegram_first_name,
                :vless_uuid, :hysteria2_password, :ss2022_password
            )
        ''', user_data2)
        db.commit()


# Импорт sqlite3 для теста
import sqlite3
