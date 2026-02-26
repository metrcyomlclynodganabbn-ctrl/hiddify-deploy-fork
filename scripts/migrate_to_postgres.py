#!/usr/bin/env python3
"""
Миграция данных из SQLite в PostgreSQL

Скрипт переносит данные из существующей SQLite базы в PostgreSQL.
Создаёт необходимые таблицы и индексы.

Использование:
    python scripts/migrate_to_postgres.py --dry-run  # Проверка без миграции
    python scripts/migrate_to_postgres.py --migrate  # Выполнение миграции
"""

import os
import sys
import sqlite3
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# Добавляем родительскую директорию в path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg
except ImportError:
    print("❌ asyncpg не установлен. Установите: pip install asyncpg")
    sys.exit(1)

# Конфигурация
SQLITE_DB_PATH = os.getenv('DB_PATH', 'data/bot.db')
POSTGRES_URL = os.getenv('DATABASE_URL', 'postgresql://hiddify_user:password@localhost:5432/hiddify_bot')


class SQLiteToPostgresMigrator:
    """Мигратор данных из SQLite в PostgreSQL"""

    def __init__(self, sqlite_path: str, postgres_url: str):
        """Инициализация мигратора

        Args:
            sqlite_path: Путь к SQLite базе
            postgres_url: URL подключения к PostgreSQL
        """
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.sqlite_conn = None
        self.pg_conn = None

    def connect_sqlite(self):
        """Подключиться к SQLite"""
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        print(f"✅ Подключено к SQLite: {self.sqlite_path}")

    async def connect_postgres(self):
        """Подключиться к PostgreSQL"""
        self.pg_conn = await asyncpg.connect(self.postgres_url)
        print(f"✅ Подключено к PostgreSQL")

    def close_sqlite(self):
        """Закрыть SQLite соединение"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            print("📌 SQLite соединение закрыто")

    async def close_postgres(self):
        """Закрыть PostgreSQL соединение"""
        if self.pg_conn:
            await self.pg_conn.close()
            print("📌 PostgreSQL соединение закрыто")

    async def create_tables(self):
        """Создать таблицы в PostgreSQL"""
        print("📝 Создание таблиц в PostgreSQL...")

        # Таблица users
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'user',
                invite_code VARCHAR(255) UNIQUE,
                invited_by BIGINT,
                data_limit_bytes BIGINT,
                used_bytes BIGINT DEFAULT 0,
                expires_at TIMESTAMP,
                is_trial BOOLEAN DEFAULT FALSE,
                trial_expiry TIMESTAMP,
                trial_activated BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица invites
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                id SERIAL PRIMARY KEY,
                code VARCHAR(255) UNIQUE NOT NULL,
                created_by BIGINT NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица subscriptions (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(telegram_id),
                plan_code VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                auto_renew BOOLEAN DEFAULT FALSE,
                data_limit_bytes BIGINT,
                used_bytes BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица payments (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                provider_id VARCHAR(255) UNIQUE,
                user_id BIGINT NOT NULL REFERENCES users(telegram_id),
                amount DECIMAL(10, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                provider VARCHAR(50) NOT NULL,
                checkout_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP
            )
        """)

        # Таблица support_tickets (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(telegram_id),
                status VARCHAR(50) DEFAULT 'open',
                category VARCHAR(50) NOT NULL,
                priority VARCHAR(50) DEFAULT 'normal',
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                admin_notes TEXT
            )
        """)

        # Таблица ticket_messages (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id SERIAL PRIMARY KEY,
                ticket_id INTEGER NOT NULL REFERENCES support_tickets(id),
                user_id BIGINT NOT NULL,
                message TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица referrals (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL REFERENCES users(telegram_id),
                referred_id BIGINT NOT NULL REFERENCES users(telegram_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bonus_amount DECIMAL(10, 2) DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'pending',
                UNIQUE(referred_id)
            )
        """)

        # Таблица promo_codes (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(255) UNIQUE NOT NULL,
                type VARCHAR(50) NOT NULL,
                value DECIMAL(10, 2) NOT NULL,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица promo_usage (новая)
        await self.pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_usage (
                id SERIAL PRIMARY KEY,
                promo_code_id INTEGER NOT NULL REFERENCES promo_codes(id),
                user_id BIGINT NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(promo_code_id, user_id)
            )
        """)

        print("✅ Таблицы созданы")

    async def create_indexes(self):
        """Создать индексы в PostgreSQL"""
        print("📝 Создание индексов...")

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_invited_by ON users(invited_by)",
            "CREATE INDEX IF NOT EXISTS idx_invites_code ON invites(code)",
            "CREATE INDEX IF NOT EXISTS idx_invites_created_by ON invites(created_by)",
            "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)",
            "CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)",
            "CREATE INDEX IF NOT EXISTS idx_payments_provider_id ON payments(provider_id)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON support_tickets(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status)",
            "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages(ticket_id)",
            "CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id)",
            "CREATE INDEX IF NOT EXISTS idx_referrals_referred_id ON referrals(referred_id)",
        ]

        for index_sql in indexes:
            await self.pg_conn.execute(index_sql)

        print("✅ Индексы созданы")

    async def migrate_users(self, dry_run: bool = False):
        """Мигрировать пользователей

        Args:
            dry_run: Проверка без записи
        """
        print("📝 Миграция users...")

        cursor = self.sqlite_conn.execute("SELECT * FROM users")
        users = cursor.fetchall()

        print(f"   Найдено {len(users)} пользователей")

        if dry_run:
            for user in users[:3]:  # Показать первые 3
                print(f"   - {user['telegram_id']}: {user.get('username', 'N/A')}")
            return

        for user in users:
            await self.pg_conn.execute(
                """INSERT INTO users
                (telegram_id, username, first_name, last_name, role, invite_code,
                 invited_by, data_limit_bytes, used_bytes, expires_at, is_trial,
                 trial_expiry, trial_activated, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (telegram_id) DO NOTHING""",
                user['telegram_id'], user.get('username'), user.get('first_name'),
                user.get('last_name'), user.get('role', 'user'), user.get('invite_code'),
                user.get('invited_by'), user.get('data_limit_bytes'), user.get('used_bytes', 0),
                user.get('expires_at'), user.get('is_trial', False),
                user.get('trial_expiry'), user.get('trial_activated', False),
                user.get('created_at')
            )

        print(f"✅ Мигрировано {len(users)} пользователей")

    async def migrate_invites(self, dry_run: bool = False):
        """Мигрировать инвайты

        Args:
            dry_run: Проверка без записи
        """
        print("📝 Миграция invites...")

        cursor = self.sqlite_conn.execute("SELECT * FROM invites")
        invites = cursor.fetchall()

        print(f"   Найдено {len(invites)} инвайтов")

        if dry_run:
            for invite in invites[:3]:
                print(f"   - {invite['code']}: {invite['used_count']}/{invite['max_uses']}")
            return

        for invite in invites:
            await self.pg_conn.execute(
                """INSERT INTO invites
                (code, created_by, max_uses, used_count, is_active, expires_at, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                invite['code'], invite['created_by'], invite['max_uses'],
                invite['used_count'], invite['is_active'], invite.get('expires_at'),
                invite['created_at']
            )

        print(f"✅ Мигрировано {len(invites)} инвайтов")

    async def run(self, dry_run: bool = False):
        """Запустить миграцию

        Args:
            dry_run: Проверка без записи
        """
        print("\n" + "="*50)
        print("🔄 Миграция SQLite → PostgreSQL")
        print("="*50 + "\n")

        if dry_run:
            print("⚠️  РЕЖИМ ПРОВЕРКИ (без записи данных)\n")

        self.connect_sqlite()
        asyncio.create_task(self.connect_postgres())

        try:
            # Создание таблиц
            if not dry_run:
                await self.create_tables()
                await self.create_indexes()

            # Миграция данных
            await self.migrate_users(dry_run)
            await self.migrate_invites(dry_run)

            print("\n" + "="*50)
            if dry_run:
                print("✅ Проверка завершена")
            else:
                print("✅ Миграция завершена")
            print("="*50 + "\n")

        finally:
            self.close_sqlite()
            await self.close_postgres()


async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="Миграция SQLite → PostgreSQL")
    parser.add_argument('--dry-run', action='store_true', help='Проверка без миграции')
    parser.add_argument('--migrate', action='store_true', help='Выполнить миграцию')
    args = parser.parse_args()

    if not args.dry_run and not args.migrate:
        parser.print_help()
        print("\nИспользуйте --dry-run для проверки или --migrate для миграции")
        return

    migrator = SQLiteToPostgresMigrator(SQLITE_DB_PATH, POSTGRES_URL)
    await migrator.run(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
