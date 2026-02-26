"""
Промокод система для скидок

Модуль обеспечивает управление промокодами для скидок на подписки.
Промокоды хранятся в БД и применяются при создании платежа.
"""

import os
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from ..database.connection import get_db_connection
from ..database.models import ValidationError

logger = logging.getLogger(__name__)


class PromoCodeError(Exception):
    """Исключение для ошибок промокодов"""
    pass


class PromoCodeType:
    """Типы промокодов"""
    PERCENT = "percent"  # Процент скидки
    FIXED = "fixed"  # Фиксированная сумма
    TRIAL = "trial"  # Пробный период


class PromoCodeClient:
    """
    Клиент для работы с промокодами

    Промокоды хранятся в таблице promo_codes:
    - code: Код промокода
    - type: Тип скидки (percent/fixed/trial)
    - value: Значение скидки
    - max_uses: Максимальное количество использований
    - used_count: Текущее количество использований
    - expires_at: Срок действия
    - is_active: Активен ли код
    - created_at: Дата создания
    """

    async def create_promo_code(
        self,
        code: str,
        promo_type: str,
        value: float,
        max_uses: int = None,
        expires_days: int = None,
        created_by: int = None
    ) -> Dict:
        """Создать новый промокод

        Args:
            code: Код промокода
            promo_type: Тип (percent/fixed/trial)
            value: Значение скидки (процент или сумма)
            max_uses: Максимальное количество использований
            expires_days: Срок действия в днях
            created_by: Telegram ID создателя

        Returns:
            Словарь с данными созданного промокода
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                # Проверка существования
                existing = await conn.execute(
                    "SELECT id FROM promo_codes WHERE code = ?",
                    (code.upper(),)
                )
                if existing.fetchone():
                    raise PromoCodeError(f"Промокод {code} уже существует")

                # Расчет срока действия
                expires_at = None
                if expires_days:
                    expires_at = datetime.now() + timedelta(days=expires_days)

                # Создание промокода
                await conn.execute(
                    """INSERT INTO promo_codes
                    (code, type, value, max_uses, used_count, expires_at, is_active, created_by, created_at)
                    VALUES (?, ?, ?, ?, 0, ?, 1, ?, ?)""",
                    (code.upper(), promo_type, value, max_uses, expires_at, created_by, datetime.now())
                )
                await conn.commit()

                # Получение созданного промокода
                row = await conn.execute(
                    "SELECT * FROM promo_codes WHERE code = ?",
                    (code.upper(),)
                )
                result = row.fetchone()

                logger.info(f"Промокод {code} создан пользователем {created_by}")

                return {
                    'id': result[0],
                    'code': result[1],
                    'type': result[2],
                    'value': result[3],
                    'max_uses': result[4],
                    'used_count': result[5],
                    'expires_at': result[6],
                    'is_active': result[7],
                    'created_by': result[8],
                    'created_at': result[9]
                }

        except Exception as e:
            logger.error(f"Ошибка создания промокода: {e}")
            raise PromoCodeError(f"Ошибка создания промокода: {e}")

    async def validate_promo_code(
        self,
        code: str,
        user_id: int = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Валидировать промокод

        Args:
            code: Код промокода
            user_id: ID пользователя (для проверки использования)

        Returns:
            (is_valid, message, promo_data)
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                # Поиск промокода
                row = await conn.execute(
                    """SELECT * FROM promo_codes WHERE code = ? AND is_active = 1""",
                    (code.upper(),)
                )
                promo = row.fetchone()

                if not promo:
                    return False, "Промокод не найден", None

                # Распаковка данных
                promo_data = {
                    'id': promo[0],
                    'code': promo[1],
                    'type': promo[2],
                    'value': promo[3],
                    'max_uses': promo[4],
                    'used_count': promo[5],
                    'expires_at': promo[6],
                    'is_active': promo[7]
                }

                # Проверка срока действия
                if promo_data['expires_at']:
                    if datetime.now() > promo_data['expires_at']:
                        return False, "Промокод истёк", None

                # Проверка лимита использований
                if promo_data['max_uses'] and promo_data['used_count'] >= promo_data['max_uses']:
                    return False, "Промокод полностью использован", None

                # Проверка повторного использования пользователем
                if user_id:
                    user_usage = await conn.execute(
                        """SELECT COUNT(*) FROM promo_usage
                        WHERE promo_code_id = ? AND user_id = ?""",
                        (promo_data['id'], user_id)
                    )
                    if user_usage.fetchone()[0] > 0:
                        return False, "Вы уже использовали этот промокод", None

                return True, "Промокод действителен", promo_data

        except Exception as e:
            logger.error(f"Ошибка валидации промокода: {e}")
            return False, "Ошибка проверки промокода", None

    async def use_promo_code(
        self,
        promo_code_id: int,
        user_id: int
    ) -> Dict:
        """Использовать промокод

        Args:
            promo_code_id: ID промокода
            user_id: ID пользователя

        Returns:
            Словарь с данными использования
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                # Проверка повторного использования
                existing = await conn.execute(
                    """SELECT id FROM promo_usage
                    WHERE promo_code_id = ? AND user_id = ?""",
                    (promo_code_id, user_id)
                )
                if existing.fetchone():
                    raise PromoCodeError("Промокод уже использован")

                # Запись использования
                await conn.execute(
                    """INSERT INTO promo_usage (promo_code_id, user_id, used_at)
                    VALUES (?, ?, ?)""",
                    (promo_code_id, user_id, datetime.now())
                )

                # Обновление счётчика использований
                await conn.execute(
                    """UPDATE promo_codes SET used_count = used_count + 1
                    WHERE id = ?""",
                    (promo_code_id,)
                )
                await conn.commit()

                # Получение обновлённых данных
                row = await conn.execute(
                    "SELECT * FROM promo_codes WHERE id = ?",
                    (promo_code_id,)
                )
                promo = row.fetchone()

                logger.info(f"Промокод {promo[1]} использован пользователем {user_id}")

                return {
                    'id': promo[0],
                    'code': promo[1],
                    'type': promo[2],
                    'value': promo[3],
                    'used_count': promo[5],
                    'is_active': promo[7]
                }

        except Exception as e:
            logger.error(f"Ошибка использования промокода: {e}")
            raise PromoCodeError(f"Ошибка использования промокода: {e}")

    async def calculate_discount(
        self,
        promo_code: str,
        original_amount: Decimal,
        user_id: int = None
    ) -> Tuple[Decimal, Decimal, str]:
        """Рассчитать скидку

        Args:
            promo_code: Код промокода
            original_amount: Исходная сумма
            user_id: ID пользователя

        Returns:
            (discount_amount, final_amount, promo_type)
        """
        is_valid, message, promo_data = await self.validate_promo_code(promo_code, user_id)

        if not is_valid:
            raise PromoCodeError(message)

        promo_type = promo_data['type']
        value = Decimal(str(promo_data['value']))

        if promo_type == PromoCodeType.PERCENT:
            discount = original_amount * value / 100
        elif promo_type == PromoCodeType.FIXED:
            discount = value
        elif promo_type == PromoCodeType.TRIAL:
            discount = original_amount  # Полная скидка для триала
        else:
            discount = Decimal("0.00")

        final_amount = max(original_amount - discount, Decimal("0.00"))

        return discount, final_amount, promo_type

    async def list_promo_codes(
        self,
        active_only: bool = True,
        created_by: int = None
    ) -> List[Dict]:
        """Получить список промокодов

        Args:
            active_only: Только активные
            created_by: Фильтр по создателю

        Returns:
            Список промокодов
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                query = "SELECT * FROM promo_codes WHERE 1=1"
                params = []

                if active_only:
                    query += " AND is_active = 1"
                if created_by:
                    query += " AND created_by = ?"
                    params.append(created_by)

                query += " ORDER BY created_at DESC"

                rows = await conn.execute(query, params)
                results = []

                for row in rows.fetchall():
                    results.append({
                        'id': row[0],
                        'code': row[1],
                        'type': row[2],
                        'value': row[3],
                        'max_uses': row[4],
                        'used_count': row[5],
                        'expires_at': row[6],
                        'is_active': row[7],
                        'created_by': row[8],
                        'created_at': row[9]
                    })

                return results

        except Exception as e:
            logger.error(f"Ошибка получения списка промокодов: {e}")
            return []


# Глобальный экземпляр клиента
promo_client = PromoCodeClient()
