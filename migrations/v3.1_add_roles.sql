-- Миграция v3.1: Система ролей пользователей
-- Добавляет колонку role для управления правами доступа
--
-- Роли:
--   'user'    - обычный пользователь (может управлять только своим аккаунтом)
--   'manager' - менеджер (может приглашать пользователей, видеть статистику)
--   'admin'   - администратор (полные права)
--
-- Дата: 2026-02-26

-- Добавить колонку role в таблицу users
ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user';

-- Создать индекс для быстрого поиска по ролям
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Обновить существующих пользователей:
-- 1. TELEGRAM_ADMIN_ID становится admin
-- 2. Все остальные остаются user (это значение по умолчанию)

-- Важно: TELEGRAM_ADMIN_ID должен быть установлен в .env
-- После миграции нужно выполнить:
--   UPDATE users SET role = 'admin' WHERE telegram_id = TELEGRAM_ADMIN_ID;

-- Добавить комментарии для документации
COMMENT ON COLUMN users.role IS 'Роль пользователя: user, manager, admin';

-- Проверка миграции
SELECT 'Migration v3.1 completed' AS status;

-- Вывод статистики
SELECT
    role,
    COUNT(*) as count
FROM users
GROUP BY role
ORDER BY count DESC;
