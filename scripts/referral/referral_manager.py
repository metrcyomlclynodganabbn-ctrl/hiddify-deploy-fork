"""
Менеджер реферальной системы

Модуль обеспечивает управление реферальной программой:
- Генерация реферальных ссылок
- Начисление бонусов
- Статистика приглашённых
"""

import os
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal

from scripts.database.connection import get_db_connection
from scripts.database.models import ReferralCreate, ReferralResponse, ReferralStats

logger = logging.getLogger(__name__)


class ReferralError(Exception):
    """Исключение для ошибок реферальной системы"""
    pass


class ReferralManager:
    """
    Менеджер для работы с реферальной системой

    Реферальные записи хранятся в таблице referrals:
    - referrer_id: ID пригласившего
    - referred_id: ID приглашённого
    - bonus_amount: Заработанная сумма
    - status: Статус (active/pending/paid)
    - created_at: Дата создания
    """

    # Настройки бонусов
    REFERRAL_BONUS_AMOUNT = Decimal("1.00")  # Бонус за реферала
    REFERRAL_BONUS_CURRENCY = "USD"

    async def create_referral(
        self,
        referrer_id: int,
        referred_id: int
    ) -> ReferralResponse:
        """Создать реферальную запись

        Args:
            referrer_id: ID пригласившего
            referred_id: ID приглашённого

        Returns:
            ReferralResponse с данными созданной записи

        Raises:
            ReferralError: Ошибка создания
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                # Проверка существования
                existing = await conn.execute(
                    """SELECT id FROM referrals
                    WHERE referred_id = ?""",
                    (referred_id,)
                )
                if existing.fetchone():
                    raise ReferralError("Пользователь уже был приглашён")

                # Проверка самореферала
                if referrer_id == referred_id:
                    raise ReferralError("Нельзя пригласить самого себя")

                # Создание записи
                now = datetime.now()
                cursor = await conn.execute(
                    """INSERT INTO referrals
                    (referrer_id, referred_id, bonus_amount, status, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (referrer_id, referred_id, self.REFERRAL_BONUS_AMOUNT, 'pending', now)
                )
                referral_id = cursor.lastrowid
                await conn.commit()

                logger.info(f"Реферал создан: {referrer_id} -> {referred_id}")

                return ReferralResponse(
                    id=referral_id,
                    referrer_id=referrer_id,
                    referred_id=referred_id,
                    created_at=now,
                    bonus_amount=self.REFERRAL_BONUS_AMOUNT,
                    status='pending'
                )

        except Exception as e:
            logger.error(f"Ошибка создания реферала: {e}")
            raise ReferralError(f"Ошибка создания реферала: {e}")

    async def get_referral_by_referred(
        self,
        referred_id: int
    ) -> Optional[ReferralResponse]:
        """Получить реферальную запись по приглашённому

        Args:
            referred_id: ID приглашённого

        Returns:
            ReferralResponse или None
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                row = await conn.execute(
                    """SELECT * FROM referrals
                    WHERE referred_id = ?""",
                    (referred_id,)
                )
                result = row.fetchone()

                if not result:
                    return None

                return ReferralResponse(
                    id=result[0],
                    referrer_id=result[1],
                    referred_id=result[2],
                    created_at=result[3],
                    bonus_amount=Decimal(str(result[4])),
                    status=result[5]
                )

        except Exception as e:
            logger.error(f"Ошибка получения реферала: {e}")
            return None

    async def get_user_referrals(
        self,
        referrer_id: int,
        limit: int = 100
    ) -> List[ReferralResponse]:
        """Получить список рефералов пользователя

        Args:
            referrer_id: ID пригласившего
            limit: Лимит записей

        Returns:
            Список рефералов
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                rows = await conn.execute(
                    """SELECT r.*, u.username, u.first_name
                    FROM referrals r
                    LEFT JOIN users u ON r.referred_id = u.telegram_id
                    WHERE r.referrer_id = ?
                    ORDER BY r.created_at DESC
                    LIMIT ?""",
                    (referrer_id, limit)
                )
                results = []

                for row in rows.fetchall():
                    results.append({
                        'id': row[0],
                        'referrer_id': row[1],
                        'referred_id': row[2],
                        'created_at': row[3],
                        'bonus_amount': Decimal(str(row[4])),
                        'status': row[5],
                        'referred_username': row[6],
                        'referred_first_name': row[7]
                    })

                return results

        except Exception as e:
            logger.error(f"Ошибка получения списка рефералов: {e}")
            return []

    async def get_referral_stats(
        self,
        referrer_id: int
    ) -> ReferralStats:
        """Получить статистику рефералов пользователя

        Args:
            referrer_id: ID пригласившего

        Returns:
            ReferralStats со статистикой
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                # Общее количество
                total_row = await conn.execute(
                    """SELECT COUNT(*) FROM referrals
                    WHERE referrer_id = ?""",
                    (referrer_id,)
                )
                total_referrals = total_row.fetchone()[0]

                # Активные (статус active)
                active_row = await conn.execute(
                    """SELECT COUNT(*) FROM referrals
                    WHERE referrer_id = ? AND status = 'active'""",
                    (referrer_id,)
                )
                active_referrals = active_row.fetchone()[0]

                # Общий заработок
                earned_row = await conn.execute(
                    """SELECT COALESCE(SUM(bonus_amount), 0) FROM referrals
                    WHERE referrer_id = ? AND status IN ('active', 'paid')""",
                    (referrer_id,)
                )
                total_earned = Decimal(str(earned_row.fetchone()[0]))

                # Ожидает выплаты
                pending_row = await conn.execute(
                    """SELECT COALESCE(SUM(bonus_amount), 0) FROM referrals
                    WHERE referrer_id = ? AND status = 'pending'""",
                    (referrer_id,)
                )
                pending_payout = Decimal(str(pending_row.fetchone()[0]))

                return ReferralStats(
                    total_referrals=total_referrals,
                    active_referrals=active_referrals,
                    total_earned=total_earned,
                    pending_payout=pending_payout
                )

        except Exception as e:
            logger.error(f"Ошибка получения статистики рефералов: {e}")
            return ReferralStats(
                total_referrals=0,
                active_referrals=0,
                total_earned=Decimal("0.00"),
                pending_payout=Decimal("0.00")
            )

    async def activate_referral(
        self,
        referral_id: int
    ) -> bool:
        """Активировать реферала (после оплаты приглашённым)

        Args:
            referral_id: ID реферала

        Returns:
            True если успешно
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                await conn.execute(
                    """UPDATE referrals SET status = 'active'
                    WHERE id = ?""",
                    (referral_id,)
                )
                await conn.commit()

                logger.info(f"Реферал #{referral_id} активирован")

                return True

        except Exception as e:
            logger.error(f"Ошибка активации реферала: {e}")
            return False

    async def generate_referral_link(
        self,
        referrer_id: int,
        bot_username: str = None
    ) -> str:
        """Сгенерировать реферальную ссылку

        Args:
            referrer_id: ID пригласившего
            bot_username: Имя бота (из .env если не указан)

        Returns:
            Реферальная ссылка
        """
        if not bot_username:
            bot_username = os.getenv('TELEGRAM_BOT_USERNAME', 'SKRTvpnbot')

        return f"https://t.me/{bot_username}?start=ref_{referrer_id}"

    async def parse_referral_code(
        self,
        start_parameter: str
    ) -> Optional[int]:
        """Парсить реферальный код из start параметра

        Args:
            start_parameter: Параметр /start

        Returns:
            ID реферера или None
        """
        if start_parameter and start_parameter.startswith('ref_'):
            try:
                referrer_id = int(start_parameter.split('_')[1])
                return referrer_id
            except (ValueError, IndexError):
                pass
        return None

    async def mark_referral_as_paid(
        self,
        referral_id: int
    ) -> bool:
        """Пометить реферал как оплаченный

        Args:
            referral_id: ID реферала

        Returns:
            True если успешно
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                await conn.execute(
                    """UPDATE referrals SET status = 'paid'
                    WHERE id = ?""",
                    (referral_id,)
                )
                await conn.commit()

                logger.info(f"Реферал #{referral_id} помечен как оплаченный")

                return True

        except Exception as e:
            logger.error(f"Ошибка пометки реферала как оплаченного: {e}")
            return False


# Глобальный экземпляр менеджера
referral_manager = ReferralManager()
