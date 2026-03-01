"""
Unit tests for Hiddify Bot handlers.
Tests /start handler, payments, and promo codes.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    Update,
    User as TelegramUser,
    Chat,
    SuccessfulPayment,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.user_handlers import cmd_start, callback_plan_selected
from bot.handlers.payment_handlers import (
    callback_pay_cryptobot,
    on_successful_payment,
    message_promo_code,
)
from bot.handlers.admin_handlers import handle_admin_users
from database.models import User, Payment, PaymentProvider, PaymentStatus
from database import crud


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_bot():
    """Mock Telegram bot."""
    bot = Mock(spec=Bot)
    bot.id = 123
    return bot


@pytest.fixture
def mock_user():
    """Mock Telegram user."""
    return TelegramUser(
        id=123456,
        is_bot=False,
        first_name="Test",
        username="testuser",
    )


@pytest.fixture
def mock_message(mock_user, mock_bot):
    """Mock Telegram message."""
    message = Mock(spec=Message)
    message.message_id = 1
    message.from_user = mock_user
    message.chat = Chat(id=123456, type="private")
    message.bot = mock_bot
    message.text = "/start"
    message.reply_markup = None
    message.answer = AsyncMock()

    # AsyncMock for edit_text
    async def edit_text_stub(*args, **kwargs):
        return Mock()

    message.edit_text = AsyncMock(side_effect=edit_text_stub)

    return message


@pytest.fixture
def mock_callback(mock_user, mock_bot):
    """Mock callback query."""
    callback = Mock(spec=CallbackQuery)
    callback.id = "callback_123"
    callback.from_user = mock_user
    callback.message = mock_message(mock_user, mock_bot)
    callback.data = "test_data"
    callback.answer = AsyncMock()

    return callback


@pytest.fixture
def test_user():
    """Create test user in database."""
    user = User(
        telegram_id=123456,
        telegram_username="testuser",
        telegram_first_name="Test",
        is_active=True,
        is_trial=False,
        vless_uuid="test-uuid-123",
        vless_enabled=True,
        data_limit_bytes=50 * 1024**3,  # 50 GB
        used_bytes=0,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=30),
    )
    return user


# ============================================================================
# /start HANDLER TESTS
# ============================================================================

class TestStartHandler:
    """Tests for /start command handler."""

    @pytest.mark.asyncio
    async def test_start_basic(self, mock_message, db_session, test_user):
        """Test basic /start command."""
        # Mock user from database
        with patch('bot.handlers.user_handlers.crud.get_or_create_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('bot.handlers.user_handlers.settings') as mock_settings:
                mock_settings.admin_ids = []
                mock_settings.bot_username = "testbot"

                await cmd_start(mock_message, db_session, test_user)

                # Verify answer was called
                mock_message.answer.assert_called_once()
                call_args = mock_message.answer.call_args
                assert "Добро пожаловать" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_start_with_invite_code(self, mock_message, db_session, test_user):
        """Test /start with invite code."""
        mock_message.text = "/start INV_TEST123"

        with patch('bot.handlers.user_handlers.crud.validate_invite_code') as mock_validate:
            mock_validate.return_value = Mock(used_count=0, max_uses=100)

            with patch('bot.handlers.user_handlers.crud.use_invite_code') as mock_use:
                mock_use.return_value = {'success': True}

                with patch('bot.handlers.user_handlers.settings') as mock_settings:
                    mock_settings.admin_ids = []
                    mock_settings.bot_username = "testbot"

                    await cmd_start(mock_message, db_session, test_user)

                    # Verify invite code was used
                    mock_use.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_referral_link(self, mock_message, db_session, test_user):
        """Test /start with referral link."""
        mock_message.text = "/start ref_999999"

        with patch('bot.handlers.user_handlers.crud.create_referral') as mock_referral:
            mock_referral.return_value = Mock(id=1)

            with patch('bot.handlers.user_handlers.settings') as mock_settings:
                mock_settings.admin_ids = []
                mock_settings.bot_username = "testbot"
                mock_settings.referral_bonus = 1.0

                await cmd_start(mock_message, db_session, test_user)

                # Verify referral was created
                mock_referral.assert_called_once()


# ============================================================================
# CRYPTOBOT PAYMENT TESTS
# ============================================================================

class TestCryptoBotPayment:
    """Tests for CryptoBot payment flow."""

    @pytest.mark.asyncio
    async def test_cryptobot_invoice_creation(self, mock_callback, db_session, test_user):
        """Test CryptoBot invoice creation."""
        # Set state with plan data
        state = Mock()
        state.get_data = AsyncMock(return_value={
            'plan_key': 'weekly',
            'plan_code': 'weekly',
            'plan_name': 'Неделя',
            'price_usd': 3.00,
            'duration_days': 7,
            'data_limit_gb': 10,
        })
        state.update_data = AsyncMock()

        mock_callback.data = "pay_cryptobot"

        with patch('bot.handlers.payment_handlers.settings') as mock_settings:
            mock_settings.cryptobot_api_token = "test_token"

            with patch('httpx.AsyncClient') as mock_httpx:
                # Mock API response
                mock_response = Mock()
                mock_response.json.return_value = {
                    "ok": True,
                    "result": {
                        "invoice_id": 12345,
                        "pay_url": "https://pay.crypt.bot/...",
                        "mini_app_url": "https://t.me/CryptoBot/...",
                    }
                }
                mock_response.raise_for_status = Mock()

                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client

                mock_httpx.return_value = mock_client

                with patch('bot.handlers.payment_handlers.crud.create_payment') as mock_create_payment:
                    mock_payment = Mock()
                    mock_payment.id = 999
                    mock_payment.provider_payment_id = ""
                    mock_create_payment.return_value = mock_payment

                    await callback_pay_cryptobot(mock_callback, state, db_session, test_user)

                    # Verify payment was created
                    mock_create_payment.assert_called_once()

                    # Verify invoice was fetched
                    mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cryptobot_no_token(self, mock_callback, db_session, test_user):
        """Test CryptoBot without API token."""
        state = Mock()
        state.get_data = AsyncMock(return_value={'plan_key': 'weekly'})

        with patch('bot.handlers.payment_handlers.settings') as mock_settings:
            mock_settings.cryptobot_api_token = None

            await callback_pay_cryptobot(mock_callback, state, db_session, test_user)

            # Verify error message
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "не настроен" in call_args[0][0]


# ============================================================================
# TELEGRAM STARS PAYMENT TESTS
# ============================================================================

class TestTelegramStarsPayment:
    """Tests for Telegram Stars payment flow."""

    @pytest.mark.asyncio
    async def test_successful_payment_activation(self, mock_message, db_session, test_user):
        """Test successful Telegram Stars payment activation."""
        # Create successful payment object
        successful_payment = Mock(spec=SuccessfulPayment)
        successful_payment.invoice_payload = "999"  # Our payment ID
        successful_payment.currency = "XTR"
        successful_payment.total_amount = 200

        # Mock payment in database
        mock_payment = Mock()
        mock_payment.status = PaymentStatus.PENDING
        mock_payment.provider = PaymentProvider.TELEGRAM_STARS
        mock_payment.plan_code = "weekly"
        mock_payment.duration_days = 7
        mock_payment.data_limit_gb = 10

        with patch('bot.handlers.payment_handlers.crud.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('sqlalchemy.asyncio.AsyncSession.get') as mock_get:
                mock_get.return_value = mock_payment

                await on_successful_payment(mock_message, successful_payment, db_session)

                # Verify success message
                mock_message.answer.assert_called_once()
                call_args = mock_message.answer.call_args
                assert "Оплата прошла успешно" in call_args[0][0]


# ============================================================================
# PROMO CODE TESTS
# ============================================================================

class TestPromoCode:
    """Tests for promo code system."""

    @pytest.mark.asyncio
    async def test_promo_code_percent_discount(self, mock_message, db_session, test_user):
        """Test promo code with percent discount."""
        mock_message.text = "SAVE20"

        state = Mock()
        state.update_data = AsyncMock()
        state.clear = AsyncMock()

        # Mock promo code validation
        mock_promo = Mock()
        mock_promo.id = 1
        mock_promo.promo_type = "percent"
        mock_promo.value = Decimal("20.00")

        with patch('bot.handlers.payment_handlers.crud.validate_promo_code') as mock_validate:
            mock_validate.return_value = (True, "Промокод действителен", mock_promo)

            await message_promo_code(mock_message, state, db_session, test_user)

            # Verify discount saved to state
            state.update_data.assert_called_once()
            call_kwargs = state.update_data.call_args[1]
            assert 'promo_discount_percent' in call_kwargs
            assert call_kwargs['promo_discount_percent'] == 20.0

    @pytest.mark.asyncio
    async def test_promo_code_invalid(self, mock_message, db_session, test_user):
        """Test invalid promo code."""
        mock_message.text = "INVALID123"

        state = Mock()

        with patch('bot.handlers.payment_handlers.crud.validate_promo_code') as mock_validate:
            mock_validate.return_value = (False, "Промокод не найден", None)

            await message_promo_code(mock_message, state, db_session, test_user)

            # Verify error message
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args
            assert "Ошибка промокода" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_promo_code_trial_activation(self, mock_message, db_session, test_user):
        """Test promo code with trial activation."""
        mock_message.text = "TRIAL7"

        state = Mock()
        state.clear = AsyncMock()

        # Mock trial promo code
        mock_promo = Mock()
        mock_promo.id = 1
        mock_promo.promo_type = "trial"
        mock_promo.value = Decimal("7.00")

        with patch('bot.handlers.payment_handlers.crud.validate_promo_code') as mock_validate:
            mock_validate.return_value = (True, "Промокод действителен", mock_promo)

            with patch('bot.handlers.payment_payments.crud.use_promo_code') as mock_use:
                await message_promo_code(mock_message, state, db_session, test_user)

                # Verify trial was activated
                assert test_user.is_trial == True
                assert test_user.expires_at is not None


# ============================================================================
# ADMIN HANDLERS TESTS
# ============================================================================

class TestAdminHandlers:
    """Tests for admin handlers."""

    @pytest.mark.asyncio
    async def test_admin_users_list(self, mock_message, db_session):
        """Test admin users list handler."""
        mock_message.text = "👥 Пользователи"

        with patch('bot.handlers.admin_handlers.settings') as mock_settings:
            mock_settings.admin_ids = [123456]  # User is admin

            with patch('bot.handlers.admin_handlers.crud.get_users_list') as mock_get_users:
                # Mock users list
                mock_user = Mock()
                mock_user.telegram_username = "user1"
                mock_user.is_active = True
                mock_user.is_trial = False
                mock_user.created_at = datetime.now()

                mock_get_users.return_value = [mock_user]

                await handle_admin_users(mock_message, db_session)

                # Verify message sent
                mock_message.answer.assert_called_once()
                call_args = mock_message.answer.call_args
                assert "Пользователи" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_admin_not_admin(self, mock_message, db_session):
        """Test admin handler for non-admin user."""
        mock_message.text = "👥 Пользователи"
        mock_message.from_user.id = 999999  # Not in admin_ids

        with patch('bot.handlers.admin_handlers.settings') as mock_settings:
            mock_settings.admin_ids = [123456]

            await handle_admin_users(mock_message, db_session)

            # Verify no message sent (user not admin)
            mock_message.answer.assert_not_called()
