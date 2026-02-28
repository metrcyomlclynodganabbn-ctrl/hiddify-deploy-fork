"""
Database setup and initialization for Hiddify Bot.
Uses SQLAlchemy 2.0 with asyncpg for PostgreSQL.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from config.settings import settings

logger = logging.getLogger(__name__)

# Import Base from models to avoid circular imports
# Base will be used by models.py
Base = declarative_base()

# Global engine and session maker
_engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Get or create async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,  # Set to True for SQL query logging
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,  # Verify connections before using
        )
        logger.info(f"Database engine created: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create async session maker."""
    global async_session_maker
    if async_session_maker is None:
        engine = get_engine()
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("Session maker created")
    return async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session for dependency injection.
    Usage in middleware/handlers:
        async with get_session() as session:
            # use session
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables if they don't exist.
    This is NOT for production use - use Alembic migrations instead.
    """
    from database.models import Base  # Import models to register them

    engine = get_engine()

    try:
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")

            # Create indexes for better performance
            await conn.run_sync(create_additional_indexes)

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def create_additional_indexes(connection) -> None:
    """
    Create additional indexes for performance.

    This function runs in sync context within run_sync().
    """
    # Index for frequently queried columns
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);",
        "CREATE INDEX IF NOT EXISTS idx_users_invite_code ON users(invite_code);",
        "CREATE INDEX IF NOT EXISTS idx_users_expires_at ON users(expires_at);",
        "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);",

        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_expires_at ON subscriptions(expires_at);",

        "CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_payments_provider ON payments(provider);",
        "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);",
        "CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);",

        "CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at);",

        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages(ticket_id);",

        "CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id);",
        "CREATE INDEX IF NOT EXISTS idx_referrals_referred_id ON referrals(referred_id);",
        "CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status);",

        "CREATE INDEX IF NOT EXISTS idx_invites_code ON invites(code);",
        "CREATE INDEX IF NOT EXISTS idx_invites_is_active ON invites(is_active);",
    ]

    for index_sql in indexes:
        try:
            connection.execute(index_sql)
        except Exception as e:
            # Ignore errors if index already exists
            logger.warning(f"Index creation warning: {e}")


async def close_db() -> None:
    """Close database connections and dispose engine."""
    global _engine, async_session_maker

    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine closed")

    async_session_maker = None
    logger.info("Database closed")


# Re-export Base for use in models.py
__all__ = [
    "Base",
    "get_engine",
    "get_session_maker",
    "get_session",
    "init_db",
    "close_db",
]
