"""
Test configuration for Hiddify Bot unit tests.

IMPORTANT: This file loads test environment BEFORE importing bot modules.
"""

import os
import sys
from pathlib import Path

# Load test environment BEFORE importing bot modules
test_env_path = Path(__file__).parent / ".env.test"
if test_env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(test_env_path, override=True)

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_session():
    """Mock database session for testing."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_user():
    """Mock user object for testing."""
    from database.models import User
    from datetime import datetime, timedelta, timezone

    user = User(
        id=1,
        telegram_id=123456789,
        telegram_username="testuser",
        telegram_first_name="Test",
        role="user",
        vless_uuid="test-uuid-12345",
        invite_code="INV_test123",
        data_limit_bytes=100 * 1024**3,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_active=True,
        is_trial=False,
        is_blocked=False,
        trial_activated=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return user


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = MagicMock()
    settings.bot_token = "test_token_12345"
    settings.bot_username = "testbot"
    settings.admin_ids = [123456789]
    settings.hiddify_api_token = "test_api_token"
    settings.db_password = "test_pass"
    settings.redis_password = "test_redis"
    settings.secret_key = "test_secret_key_for_tests"
    settings.panel_domain = "test.panel"
    settings.referral_bonus = 1.0
    settings.trial_days = 7
    settings.trial_limit_gb = 5
    return settings
