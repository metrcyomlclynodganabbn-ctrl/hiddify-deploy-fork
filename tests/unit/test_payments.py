"""Unit тесты для payment модуля"""

import pytest
from decimal import Decimal
from datetime import datetime

# Проверка наличия зависимостей
pytest.importorskip("stripe")

from scripts.database.models import (
    PaymentCreate, PaymentResponse,
    PaymentMethod, PaymentStatus, PaymentProvider
)
from scripts.payments.stripe_client import StripeClient, StripeClientError


class TestPaymentModels:
    """Тесты Pydantic моделей платежей"""

    def test_payment_create_valid(self):
        """Тест валидации PaymentCreate"""
        payment = PaymentCreate(
            user_id=123,
            amount=Decimal("10.00"),
            currency="USD",
            method=PaymentMethod.CARD,
            plan_code="monthly"
        )

        assert payment.user_id == 123
        assert payment.amount == Decimal("10.00")
        assert payment.currency == "USD"
        assert payment.method == PaymentMethod.CARD

    def test_payment_create_negative_amount_raises(self):
        """Тест отрицательной суммы"""
        with pytest.raises(ValueError):
            PaymentCreate(
                user_id=123,
                amount=Decimal("-10.00"),
                currency="USD",
                method=PaymentMethod.CARD
            )

    def test_payment_response_valid(self):
        """Тест валидации PaymentResponse"""
        payment = PaymentResponse(
            id=1,
            provider_id="cs_test123",
            user_id=123,
            amount=Decimal("10.00"),
            currency="USD",
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.STRIPE,
            checkout_url="https://checkout.stripe.com/pay/test",
            created_at=datetime.now()
        )

        assert payment.id == 1
        assert payment.provider_id == "cs_test123"
        assert payment.status == PaymentStatus.PENDING


class TestStripeClient:
    """Тесты Stripe клиента"""

    def test_stripe_client_init_without_key(self):
        """Тест инициализации без ключа"""
        client = StripeClient(secret_key="", webhook_secret="")

        # Должен создать клиента, но с пустыми ключами
        assert client.secret_key == ""
        assert client.webhook_secret == ""

    def test_stripe_status_mapping(self):
        """Тест конвертации статусов Stripe"""
        client = StripeClient(secret_key="sk_test_123")

        assert client.map_stripe_status_to_payment_status("paid") == PaymentStatus.PAID
        assert client.map_stripe_status_to_payment_status("complete") == PaymentStatus.PAID
        assert client.map_stripe_status_to_payment_status("failed") == PaymentStatus.FAILED
        assert client.map_stripe_status_to_payment_status("expired") == PaymentStatus.EXPIRED


@pytest.mark.asyncio
class TestPromoClient:
    """Тесты промокод клиента"""

    async def test_promo_code_type_constants(self):
        """Тест констант типов промокодов"""
        from scripts.payments.promo_client import PromoCodeClient, PromoCodeType

        assert PromoCodeType.PERCENT == "percent"
        assert PromoCodeType.FIXED == "fixed"
        assert PromoCodeType.TRIAL == "trial"
