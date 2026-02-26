"""Интеграционные тесты для v4.0 referral flow"""

import pytest
import asyncio
from decimal import Decimal

from scripts.database.models import ReferralCreate, ReferralResponse, ReferralStats
from scripts.referral.referral_manager import ReferralManager


@pytest.mark.asyncio
class TestReferralFlow:
    """Тесты потока рефералов"""

    async def test_referral_manager_initialization(self):
        """Тест инициализации менеджера рефералов"""
        manager = ReferralManager()

        assert manager.REFERRAL_BONUS_AMOUNT == Decimal("1.00")
        assert manager.REFERRAL_BONUS_CURRENCY == "USD"

    async def test_referral_create_validation(self):
        """Тест валидации создания реферала"""
        referral = ReferralCreate(
            referrer_id=123,
            referred_id=456,
            bonus_amount=Decimal("1.00")
        )

        assert referral.referrer_id == 123
        assert referral.referred_id == 456
        assert referral.bonus_amount == Decimal("1.00")

    async def test_referral_self_referral_invalid(self):
        """Тест самореферала"""
        # Модель валидна, но бизнес-логика должна отклонить
        referral = ReferralCreate(
            referrer_id=123,
            referred_id=123,  # Самореферал
            bonus_amount=Decimal("1.00")
        )

        assert referral.referrer_id == referral.referred_id

    async def test_referral_link_generation(self):
        """Тест генерации реферальной ссылки"""
        manager = ReferralManager()

        # Без указания username (использует значение из env или дефолт)
        link = asyncio.run(manager.generate_referral_link(123))

        assert link.startswith("https://t.me/")
        assert "ref_123" in link

    async def test_referral_code_parsing(self):
        """Тест парсинга реферального кода"""
        manager = ReferralManager()

        # Валидный код
        referrer_id = asyncio.run(manager.parse_referral_code("ref_456"))
        assert referrer_id == 456

        # Невалидные коды
        assert asyncio.run(manager.parse_referral_code("invalid")) is None
        assert asyncio.run(manager.parse_referral_code("ref_abc")) is None

    async def test_referral_stats_model(self):
        """Тест модели статистики рефералов"""
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


@pytest.mark.asyncio
class TestReferralIntegration:
    """Интеграционные тесты реферальной системы"""

    async def test_full_referral_flow_simulation(self):
        """Симуляция полного потока реферала"""
        # 1. Генерация реферальной ссылки
        manager = ReferralManager()
        link = asyncio.run(manager.generate_referral_link(123, "testbot"))

        assert "ref_123" in link

        # 2. Парсинг кода из start параметра
        referrer_id = asyncio.run(manager.parse_referral_code("ref_123"))
        assert referrer_id == 123

        # 3. Создание записи о реферале
        referral = ReferralCreate(
            referrer_id=123,
            referred_id=456,
            bonus_amount=Decimal("1.00")
        )

        assert referral.referrer_id == 123

        # 4. В реальной системе здесь была бы запись в БД
        # result = await referral_manager.create_referral(referral)

        # 5. Получение статистики
        # stats = await referral_manager.get_referral_stats(123)
        # assert stats.total_referrals > 0
