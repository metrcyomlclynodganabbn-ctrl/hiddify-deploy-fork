#!/usr/bin/env python3
"""
Migration script: SQLite → PostgreSQL.
Migrates users, payments, support tickets, and referrals from legacy SQLite database.
"""

import asyncio
import sqlite3
import os
import sys
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import get_async_session, engine
from database.models import (
    User,
    Payment,
    PaymentProvider,
    PaymentStatus,
    SupportTicket,
    TicketMessage,
    TicketCategory,
    TicketPriority,
    Referral,
    ReferralStatus,
    Invite,
    PromoCode,
    PromoCodeType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/bot.db")
BATCH_SIZE = 100  # Process records in batches


# ============================================================================
# SQLITE CONNECTION
# ============================================================================

def get_sqlite_connection():
    """Get SQLite connection."""
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database not found: {SQLITE_DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

async def migrate_users(session: AsyncSession) -> int:
    """Migrate users from SQLite to PostgreSQL."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT telegram_id, telegram_username, telegram_first_name,
                   is_active, is_trial, vless_uuid, vless_enabled,
                   data_limit_bytes, used_bytes, expires_at,
                   created_at, updated_at
            FROM users
        """)

        users_data = cursor.fetchall()
        migrated = 0

        for row in users_data:
            # Check if user already exists
            existing = await session.execute(
                select(User).where(User.telegram_id == row["telegram_id"])
            )
            if existing.scalar_one_or_none():
                logger.info(f"User {row['telegram_id']} already exists, skipping")
                continue

            user = User(
                telegram_id=row["telegram_id"],
                telegram_username=row["telegram_username"],
                telegram_first_name=row["telegram_first_name"],
                is_active=bool(row["is_active"]),
                is_trial=bool(row["is_trial"]),
                vless_uuid=row["vless_uuid"],
                vless_enabled=bool(row["vless_enabled"]),
                data_limit_bytes=row["data_limit_bytes"],
                used_bytes=row["used_bytes"],
                expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            )

            session.add(user)
            migrated += 1

            if migrated % BATCH_SIZE == 0:
                await session.commit()
                logger.info(f"Committed {migrated} users...")

        await session.commit()
        logger.info(f"✅ Users migrated: {migrated}")
        return migrated

    finally:
        conn.close()


async def migrate_payments(session: AsyncSession) -> int:
    """Migrate payments from SQLite to PostgreSQL."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, provider, provider_payment_id, amount, currency,
                   status, plan_code, duration_days, data_limit_gb,
                   created_at, completed_at
            FROM payments
        """)

        payments_data = cursor.fetchall()
        migrated = 0

        # Map legacy provider names to new enum
        provider_map = {
            "stripe": PaymentProvider.STRIPE,
            "cryptobot": PaymentProvider.CRYPTOBOT,
            "telegram_stars": PaymentProvider.TELEGRAM_STARS,
            "yoomoney": PaymentProvider.YOOMONEY,
            "promo": PaymentProvider.PROMO,
        }

        status_map = {
            "pending": PaymentStatus.PENDING,
            "completed": PaymentStatus.COMPLETED,
            "failed": PaymentStatus.FAILED,
            "refunded": PaymentStatus.REFUNDED,
            "cancelled": PaymentStatus.CANCELLED,
        }

        for row in payments_data:
            # Get user by telegram_id
            user_result = await session.execute(
                select(User).where(User.telegram_id == row["user_id"])
            )
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {row['user_id']} not found, skipping payment {row.get('id')}")
                continue

            # Skip if already exists
            existing = await session.execute(
                select(Payment)
                .where(Payment.user_id == user.id)
                .where(Payment.provider_payment_id == str(row["provider_payment_id"]))
                .where(Payment.created_at == datetime.fromisoformat(row["created_at"]))
            )
            if existing.scalar_one_or_none():
                continue

            payment = Payment(
                user_id=user.id,
                provider=provider_map.get(row["provider"], PaymentProvider.STRIPE),
                provider_payment_id=str(row["provider_payment_id"]),
                amount=Decimal(str(row["amount"])) if row["amount"] else None,
                currency=row["currency"],
                status=status_map.get(row["status"], PaymentStatus.PENDING),
                plan_code=row["plan_code"],
                duration_days=row["duration_days"],
                data_limit_gb=row["data_limit_gb"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            )

            session.add(payment)
            migrated += 1

            if migrated % BATCH_SIZE == 0:
                await session.commit()
                logger.info(f"Committed {migrated} payments...")

        await session.commit()
        logger.info(f"✅ Payments migrated: {migrated}")
        return migrated

    finally:
        conn.close()


async def migrate_support_tickets(session: AsyncSession) -> int:
    """Migrate support tickets from SQLite to PostgreSQL."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, user_id, category, priority, title,
                   description, status, created_at, updated_at
            FROM support_tickets
        """)

        tickets_data = cursor.fetchall()
        migrated = 0

        # Map category
        category_map = {
            "payment": TicketCategory.PAYMENT,
            "connection": TicketCategory.CONNECTION,
            "speed": TicketCategory.SPEED,
            "account": TicketCategory.ACCOUNT,
            "other": TicketCategory.OTHER,
        }

        for row in tickets_data:
            # Get user by telegram_id
            user_result = await session.execute(
                select(User).where(User.telegram_id == row["user_id"])
            )
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {row['user_id']} not found, skipping ticket {row['id']}")
                continue

            # Skip if exists
            existing = await session.execute(
                select(SupportTicket)
                .where(SupportTicket.user_id == user.id)
                .where(SupportTicket.title == row["title"])
            )
            if existing.scalar_one_or_none():
                continue

            ticket = SupportTicket(
                user_id=user.id,
                category=category_map.get(row["category"], TicketCategory.OTHER),
                priority=TicketPriority.NORMAL,  # Default priority
                title=row["title"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            )

            session.add(ticket)
            migrated += 1

            if migrated % BATCH_SIZE == 0:
                await session.commit()
                logger.info(f"Committed {migrated} tickets...")

        await session.commit()
        logger.info(f"✅ Support tickets migrated: {migrated}")
        return migrated

    finally:
        conn.close()


async def migrate_referrals(session: AsyncSession) -> int:
    """Migrate referrals from SQLite to PostgreSQL."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT referrer_id, referred_id, bonus_amount, status,
                   payment_id, created_at, activated_at
            FROM referrals
        """)

        referrals_data = cursor.fetchall()
        migrated = 0

        status_map = {
            "pending": ReferralStatus.PENDING,
            "active": ReferralStatus.ACTIVE,
            "completed": ReferralStatus.COMPLETED,
        }

        for row in referrals_data:
            # Get users by telegram_id
            referrer_result = await session.execute(
                select(User).where(User.telegram_id == row["referrer_id"])
            )
            referrer = referrer_result.scalar_one_or_none()

            referred_result = await session.execute(
                select(User).where(User.telegram_id == row["referred_id"])
            )
            referred = referred_result.scalar_one_or_none()

            if not referrer or not referred:
                logger.warning(f"Users not found for referral, skipping")
                continue

            # Skip if exists
            existing = await session.execute(
                select(Referral)
                .where(Referral.referrer_id == referrer.id)
                .where(Referral.referred_id == referred.id)
            )
            if existing.scalar_one_or_none():
                continue

            referral = Referral(
                referrer_id=referrer.id,
                referred_id=referred.id,
                bonus_amount=Decimal(str(row["bonus_amount"])) if row["bonus_amount"] else Decimal("0"),
                status=status_map.get(row["status"], ReferralStatus.PENDING),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            )

            session.add(referral)
            migrated += 1

            if migrated % BATCH_SIZE == 0:
                await session.commit()
                logger.info(f"Committed {migrated} referrals...")

        await session.commit()
        logger.info(f"✅ Referrals migrated: {migrated}")
        return migrated

    finally:
        conn.close()


async def migrate_invites(session: AsyncSession) -> int:
    """Migrate invite codes from SQLite to PostgreSQL."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT code, created_by, max_uses, used_count, is_active, expires_at
            FROM invites
        """)

        invites_data = cursor.fetchall()
        migrated = 0

        for row in invites_data:
            # Skip if exists
            existing = await session.execute(
                select(Invite).where(Invite.code == row["code"])
            )
            if existing.scalar_one_or_none():
                continue

            invite = Invite(
                code=row["code"],
                created_by=row["created_by"],
                max_uses=row["max_uses"],
                used_count=row["used_count"],
                is_active=bool(row["is_active"]),
                expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            )

            session.add(invite)
            migrated += 1

            if migrated % BATCH_SIZE == 0:
                await session.commit()
                logger.info(f"Committed {migrated} invites...")

        await session.commit()
        logger.info(f"✅ Invites migrated: {migrated}")
        return migrated

    finally:
        conn.close()


# ============================================================================
# MAIN MIGRATION
# ============================================================================

async def run_migration():
    """Run full migration from SQLite to PostgreSQL."""
    logger.info("🔄 Starting migration: SQLite → PostgreSQL")
    logger.info(f"Source: {SQLITE_DB_PATH}")

    # Check SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"❌ SQLite database not found: {SQLITE_DB_PATH}")
        logger.info("💡 If you don't have a SQLite database, this is normal for new installations.")
        logger.info("💡 The new bot will use PostgreSQL directly.")
        return

    async for session in get_async_session():
        try:
            # Migrate in order of dependencies
            logger.info("\n📦 Migrating users...")
            users_count = await migrate_users(session)

            logger.info("\n💳 Migrating payments...")
            payments_count = await migrate_payments(session)

            logger.info("\n💬 Migrating support tickets...")
            tickets_count = await migrate_support_tickets(session)

            logger.info("\n👥 Migrating referrals...")
            referrals_count = await migrate_referrals(session)

            logger.info("\n🎫 Migrating invites...")
            invites_count = await migrate_invites(session)

            logger.info("\n" + "=" * 50)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 50)
            logger.info(f"📊 Summary:")
            logger.info(f"  Users: {users_count}")
            logger.info(f"  Payments: {payments_count}")
            logger.info(f"  Support tickets: {tickets_count}")
            logger.info(f"  Referrals: {referrals_count}")
            logger.info(f"  Invites: {invites_count}")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
