-- === Миграция БД v2.0 → v2.1 ===
-- Добавляет поля для VLESS Reality ключей и пробного периода

-- Версия миграции: 2.1.0
-- Дата: 23 февраля 2026
-- Описание: Reality ключи, пробный период, улучшенная статистика

-- === 1. Добавление полей в таблицу users ===

-- Reality ключи (для генерации VLESS URL)
ALTER TABLE users ADD COLUMN reality_public_key TEXT;
ALTER TABLE users ADD COLUMN reality_private_key TEXT;
ALTER TABLE users ADD COLUMN reality_short_id TEXT;
ALTER TABLE users ADD COLUMN reality_sni TEXT DEFAULT 'www.apple.com';
ALTER TABLE users ADD COLUMN reality_fingerprint TEXT DEFAULT 'chrome';

-- Пробный период
ALTER TABLE users ADD COLUMN is_trial BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN trial_expiry TIMESTAMP;
ALTER TABLE users ADD COLUMN trial_data_limit_gb INTEGER DEFAULT 10;

-- Метаданные для статистики
ALTER TABLE users ADD COLUMN last_connected_at TIMESTAMP;
ALTER TABLE users ADD COLUMN connection_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN total_bytes_used BIGINT DEFAULT 0;

-- === 2. Создание индексов ===

CREATE INDEX IF NOT EXISTS idx_users_trial ON users(is_trial, trial_expiry);
CREATE INDEX IF NOT EXISTS idx_users_reality ON users(reality_short_id);
CREATE INDEX IF NOT EXISTS idx_users_last_connected ON users(last_connected_at);

-- === 3. Миграция существующих пользователей ===

-- Установка значений по умолчанию для существующих пользователей
UPDATE users
SET
    reality_sni = 'www.apple.com',
    reality_fingerprint = 'chrome',
    is_trial = FALSE,
    connection_count = 0,
    total_bytes_used = 0
WHERE reality_sni IS NULL;

-- === 4. Создание таблицы для ротации SNI (v2.1) ===

CREATE TABLE IF NOT EXISTS sni_rotation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    old_sni TEXT NOT NULL,
    new_sni TEXT NOT NULL,
    rotated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rotated_by INTEGER REFERENCES users(id)  -- NULL если системой
);

CREATE INDEX IF NOT EXISTS idx_sni_rotation_user ON sni_rotation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_sni_rotation_date ON sni_rotation_history(rotated_at);

-- === 5. Создание таблицы для QR кодов (кеширование) ===

CREATE TABLE IF NOT EXISTS qr_codes_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    protocol TEXT NOT NULL,  -- vless, hysteria2, ss2022
    qr_code_url TEXT NOT NULL,  -- Ссылка на QR код (файл или URL)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- QR коды могут истекать
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_qr_cache_user ON qr_codes_cache(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_qr_cache_protocol ON qr_codes_cache(protocol);

-- === 6. Создание таблицы для логов подключений (улучшенная статистика) ===

CREATE TABLE IF NOT EXISTS connection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    protocol TEXT NOT NULL,
    remote_ip TEXT,
    country TEXT,
    city TEXT,
    bytes_received BIGINT DEFAULT 0,
    bytes_sent BIGINT DEFAULT 0,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP,
    duration_seconds INTEGER
);

CREATE INDEX IF NOT EXISTS idx_conn_logs_user ON connection_logs(user_id, connected_at DESC);
CREATE INDEX IF NOT EXISTS idx_conn_logs_protocol ON connection_logs(protocol);

-- === 7. Комментарии к таблицам (SQLite поддерживает комментарии) ===

-- Комментарии помогают документировать структуру БД

-- === 8. Валидация данных ===

-- Проверка, что миграция прошла успешно
SELECT
    COUNT(*) as total_users,
    SUM(CASE WHEN is_trial = 1 THEN 1 ELSE 0 END) as trial_users,
    SUM(CASE WHEN reality_public_key IS NOT NULL THEN 1 ELSE 0 END) as users_with_keys
FROM users;

-- Ожидаемый результат:
-- total_users: количество пользователей
-- trial_users: 0 (новые пользователи)
-- users_with_keys: 0 (ключи будут генерироваться по требованию)

-- === Откат миграции (если нужен) ===

-- DROP INDEX IF EXISTS idx_conn_logs_protocol;
-- DROP INDEX IF EXISTS idx_conn_logs_user;
-- DROP INDEX IF EXISTS idx_qr_cache_protocol;
-- DROP INDEX IF EXISTS idx_qr_cache_user;
-- DROP TABLE IF EXISTS connection_logs;
-- DROP TABLE IF EXISTS qr_codes_cache;
-- DROP TABLE IF EXISTS sni_rotation_history;
-- DROP INDEX IF EXISTS idx_users_last_connected;
-- DROP INDEX IF EXISTS idx_users_reality;
-- DROP INDEX IF EXISTS idx_users_trial;
-- ALTER TABLE users DROP COLUMN total_bytes_used;
-- ALTER TABLE users DROP COLUMN connection_count;
-- ALTER TABLE users DROP COLUMN last_connected_at;
-- ALTER TABLE users DROP COLUMN trial_data_limit_gb;
-- ALTER TABLE users DROP COLUMN trial_expiry;
-- ALTER TABLE users DROP COLUMN is_trial;
-- ALTER TABLE users DROP COLUMN reality_fingerprint;
-- ALTER TABLE users DROP COLUMN reality_sni;
-- ALTER TABLE users DROP COLUMN reality_short_id;
-- ALTER TABLE users DROP COLUMN reality_private_key;
-- ALTER TABLE users DROP COLUMN reality_public_key;
