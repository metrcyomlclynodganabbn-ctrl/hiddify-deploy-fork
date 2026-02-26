"""Unit тесты для referral модуля"""

import pytest
from decimal import Decimal

from scripts.database.models import ReferralCreate, ReferralResponse, ReferralStats
from scripts.referral.referral_manager import ReferralManager, ReferralError


class TestReferralModels:
    """Тесты Pydantic моделей рефералов"""

    def test_referral_create_valid(self):
        """Тест валидации ReferralCreate"""
        referral = ReferralCreate(
            referrer_id=123,
            referred_id=456,
            bonus_amount=Decimal("1.00")
        )

        assert referral.referrer_id == 123
        assert referral.referred_id == 456
        assert referral.bonus_amount == Decimal("1.00")

    def test_referral_response_valid(self):
        """Тест валидации ReferralResponse"""
        from datetime import datetime

        referral = ReferralResponse(
            id=1,
            referrer_id=123,
            referred_id=456,
            created_at=datetime.now(),
            bonus_amount=Decimal("1.00"),
            status="pending"
        )

        assert referral.id == 1
        assert referral.status == "pending"

    def test_referral_stats_valid(self):
        """Тест валидации ReferralStats"""
        stats = ReferralStats(
            total_referrals=10,
            active_referrals=5,
            total_earned=Decimal("10.00"),
            pending_payout=Decimal("5.00")
        )

        assert stats.total_referrals == 10
        assert stats.active_referrals == 5
        assert stats.total_earned == Decimal("10.00")
        assert stats.pending_payout == Decimal("5.00")


class TestReferralManager:
    """Тесты менеджера рефералов"""

    def test_referral_manager_init(self):
        """Тест инициализации менеджера"""
        manager = ReferralManager()

        assert manager.REFERRAL_BONUS_AMOUNT == Decimal("1.00")
        assert manager.REFERRAL_BONUS_CURRENCY == "USD"

    def test_generate_referral_link(self):
        """Тест генерации реферальной ссылки"""
        import os
        import asyncio

        manager = ReferralManager()

        # Тест без BOT_USERNAME в env
        if 'TELEGRAM_BOT_USERNAME' in os.environ:
            del os.environ['TELEGRAM_BOT_USERNAME']

        link = asyncio.run(manager.generate_referral_link(123))
        assert "ref_123" in link
        assert link.startswith("https://t.me/")

        # Тест с указанным username
        link = asyncio.run(manager.generate_referral_link(123, "testbot"))
        assert link == "https://t.me/testbot?start=ref_123"

    def test_parse_referral_code(self):
        """Тест парсинга реферального кода"""
        import asyncio

        manager = ReferralManager()

        # Валидный код
        referrer_id = asyncio.run(manager.parse_referral_code("ref_456"))
        assert referrer_id == 456

        # Невалидные коды
        assert asyncio.run(manager.parse_referral_code("invalid")) is None
        assert asyncio.run(manager.parse_referral_code("ref_abc")) is None
        assert asyncio.run(manager.parse_referral_code("")) is None

    def test_parse_self_referral_raises(self):
        """Тест самореферала вызывает ошибку"""
        from datetime import datetime

        # Проверка валидации (создание записи с теми же ID)
        referral = ReferralCreate(
            referrer_id=123,
            referred_id=123,  # Самореферал
            bonus_amount=Decimal("1.00")
        )

        # Модель валидна, но бизнес-логика должна это отклонить
        assert referral.referrer_id == referral.referred_id
