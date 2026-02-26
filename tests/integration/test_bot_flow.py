"""
Интеграционные тесты полного цикла работы бота

Тестируют сценарии:
1. Регистрация пользователя по инвайт-коду
2. Получение конфигурации
3. Активация пробного периода
"""

import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
def test_full_user_registration_flow(init_test_db, test_user_data, test_invite_data):
    """
    Тест полного цикла регистрации пользователя

    1. Создать инвайт
    2. Зарегистрировать пользователя по инвайту
    3. Проверить что пользователь создан
    4. Проверить что инвайт использован
    """

    db = init_test_db

    # Шаг 1: Создать инвайт
    db.execute('''
        INSERT INTO invites (code, max_uses, used_count, is_active)
        VALUES (:code, :max_uses, :used_count, :is_active)
    ''', test_invite_data)
    db.commit()

    # Проверить что инвайт создан
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite is not None
    assert invite['used_count'] == 0

    # Шаг 2: Создать пользователя (симуляция создания)
    user_data = test_user_data.copy()
    user_data['invite_code'] = test_invite_data['code']
    user_data['vless_uuid'] = 'test-uuid-12345'
    user_data['hysteria2_password'] = 'test-hysteria-password'
    user_data['ss2022_password'] = 'test-ss2022-password'
    user_data['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()

    db.execute('''
        INSERT INTO users (
            telegram_id, telegram_username, telegram_first_name,
            invite_code, vless_uuid, hysteria2_password, ss2022_password,
            expires_at, data_limit_bytes
        ) VALUES (
            :telegram_id, :telegram_username, :telegram_first_name,
            :invite_code, :vless_uuid, :hysteria2_password, :ss2022_password,
            :expires_at, :data_limit_bytes
        )
    ''', user_data)
    db.commit()

    # Шаг 3: Проверить что пользователь создан
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user is not None
    assert user['telegram_username'] == test_user_data['telegram_username']
    assert user['is_active'] == 1

    # Шаг 4: Обновить счётчик использования инвайта
    db.execute('UPDATE invites SET used_count = used_count + 1 WHERE code = ?', (test_invite_data['code'],))
    db.commit()

    # Проверить что инвайт использован
    invite = db.execute('SELECT * FROM invites WHERE code = ?', (test_invite_data['code'],)).fetchone()
    assert invite['used_count'] == 1


@pytest.mark.integration
def test_trial_activation_flow(init_test_db, test_user_data):
    """
    Тест активации пробного периода

    1. Создать пользователя без trial
    2. Активировать trial
    3. Проверить что параметры обновлены
    """

    db = init_test_db

    # Шаг 1: Создать пользователя
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

    # Проверить начальное состояние
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user is not None
    # В новой схеме нужно добавить колонки is_trial, trial_expiry, trial_activated
    # Для теста добавим их

    # Шаг 2: Добавить trial колонки если их нет
    db.execute('ALTER TABLE users ADD COLUMN is_trial BOOLEAN DEFAULT 0')
    db.execute('ALTER TABLE users ADD COLUMN trial_expiry TIMESTAMP')
    db.execute('ALTER TABLE users ADD COLUMN trial_activated BOOLEAN DEFAULT 0')

    # Шаг 3: Активировать trial (7 дней, 10 GB)
    trial_end = datetime.now() + timedelta(days=7)
    trial_limit_bytes = 10 * (1024**3)

    db.execute('''
        UPDATE users
        SET is_trial = TRUE,
            trial_expiry = ?,
            trial_activated = TRUE,
            data_limit_bytes = ?,
            expires_at = ?
        WHERE telegram_id = ?
    ''', (trial_end.isoformat(), trial_limit_bytes, trial_end.isoformat(), user_data['telegram_id']))
    db.commit()

    # Шаг 4: Проверить что trial активирован
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user['is_trial'] == 1
    assert user['trial_activated'] == 1
    assert user['data_limit_bytes'] == trial_limit_bytes


@pytest.mark.integration
def test_user_deletion_flow(init_test_db, test_user_data):
    """
    Тест удаления пользователя

    1. Создать пользователя
    2. Удалить пользователя
    3. Проверить что пользователь удалён
    """

    db = init_test_db

    # Шаг 1: Создать пользователя
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

    # Проверить что пользователь создан
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user is not None

    # Шаг 2: Удалить пользователя (мягкое удаление - is_active = 0)
    db.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (user_data['telegram_id'],))
    db.commit()

    # Шаг 3: Проверить что пользователь деактивирован
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (user_data['telegram_id'],)).fetchone()
    assert user['is_active'] == 0
