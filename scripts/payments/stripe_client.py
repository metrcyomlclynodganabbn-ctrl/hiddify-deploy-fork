"""
Stripe клиент для обработки платежей

Модуль обеспечивает интеграцию со Stripe для приёма карточных платежей.
Поддерживает создание checkout сессий и обработку webhooks.

Требования:
- pip install stripe
- Stripe API ключ в .env (STRIPE_SECRET_KEY)
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import stripe
except ImportError:
    stripe = None

from scripts.database.models import (
    PaymentCreate, PaymentResponse,
    PaymentMethod, PaymentStatus, PaymentProvider
)

logger = logging.getLogger(__name__)


class StripeClientError(Exception):
    """Исключение для ошибок Stripe клиента"""
    pass


class StripeClient:
    """
    Клиент для работы с Stripe API

    Attributes:
        secret_key: Секретный ключ API Stripe
        webhook_secret: Секрет для проверки webhooks
    """

    def __init__(self, secret_key: str = None, webhook_secret: str = None):
        """Инициализация Stripe клиента

        Args:
            secret_key: Секретный ключ Stripe API
            webhook_secret: Секрет для проверки webhooks (whsec_...)
        """
        if not stripe:
            raise ImportError("stripe не установлен. Установите: pip install stripe")

        self.secret_key = secret_key or os.getenv('STRIPE_SECRET_KEY', '')
        self.webhook_secret = webhook_secret or os.getenv('STRIPE_WEBHOOK_SECRET', '')

        if not self.secret_key:
            logger.warning("STRIPE_SECRET_KEY не установлен")

        stripe.api_key = self.secret_key

    async def create_checkout_session(
        self,
        payment: PaymentCreate,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentResponse:
        """Создать платёжную сессию Stripe

        Args:
            payment: Данные для создания платежа
            success_url: URL для редиректа при успехе
            cancel_url: URL для редиректа при отмене
            metadata: Дополнительные метаданные

        Returns:
            PaymentResponse с данными сессии

        Raises:
            StripeClientError: Ошибка создания сессии
        """
        try:
            # Формирование метаданных
            session_metadata = {
                'user_id': str(payment.user_id),
                'plan_code': payment.plan_code or 'unknown',
                'currency': payment.currency
            }
            if metadata:
                session_metadata.update(metadata)

            # Создание сессии
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': payment.currency.lower(),
                        'product_data': {
                            'name': f'VPN подписка - {payment.plan_code or "Standard"}',
                            'description': f'VPN сервис: {payment.plan_code or "Standard"}',
                        },
                        'unit_amount': int(payment.amount * 100),  # В центах
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=None,  # Можно добавить email пользователя
                metadata=session_metadata,
                expires_at=int((datetime.now().timestamp() + 3600 * 24))  # 24 часа
            )

            logger.info(f"Stripe сессия создана: {session.id} для user={payment.user_id}")

            return PaymentResponse(
                id=int(session.id.replace('cs_', ''))[:10],  # Временный ID
                provider_id=session.id,
                user_id=payment.user_id,
                amount=payment.amount,
                currency=payment.currency,
                status=PaymentStatus.PENDING,
                provider=PaymentProvider.STRIPE,
                checkout_url=session.url,
                created_at=datetime.fromtimestamp(session.created)
            )

        except stripe.error.StripeError as e:
            logger.error(f"Stripe ошибка создания сессии: {e}")
            raise StripeClientError(f"Ошибка создания платёжной сессии: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            raise StripeClientError(f"Неожиданная ошибка: {e}")

    async def retrieve_session(self, session_id: str) -> Dict[str, Any]:
        """Получить данные сессии по ID

        Args:
            session_id: ID сессии Stripe (cs_...)

        Returns:
            Словарь с данными сессии

        Raises:
            StripeClientError: Ошибка получения сессии
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                'id': session.id,
                'status': session.status,
                'payment_status': session.payment_status,
                'metadata': session.metadata,
                'amount_total': session.amount_total,
                'currency': session.currency,
                'customer': session.customer,
                'created': session.created
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe ошибка получения сессии: {e}")
            raise StripeClientError(f"Ошибка получения сессии: {e}")

    async def verify_webhook_signature(
        self,
        payload: bytes,
        sig_header: str
    ) -> stripe.Event:
        """Проверить подпись webhook

        Args:
            payload: Тело webhook
            sig_header: Заголовок Stripe-Signature

        Returns:
            Объект события Stripe

        Raises:
            StripeClientError: Неверная подпись
        """
        if not self.webhook_secret:
            raise StripeClientError("STRIPE_WEBHOOK_SECRET не установлен")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Ошибка парсинга webhook: {e}")
            raise StripeClientError(f"Неверный payload: {e}")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Неверная подпись webhook: {e}")
            raise StripeClientError(f"Неверная подпись: {e}")

    def map_stripe_status_to_payment_status(
        self,
        stripe_status: str
    ) -> PaymentStatus:
        """Конвертировать статус Stripe в PaymentStatus

        Args:
            stripe_status: Статус из Stripe

        Returns:
            PaymentStatus
        """
        mapping = {
            'pending': PaymentStatus.PENDING,
            'processing': PaymentStatus.PROCESSING,
            'paid': PaymentStatus.PAID,
            'complete': PaymentStatus.PAID,
            'failed': PaymentStatus.FAILED,
            'expired': PaymentStatus.EXPIRED,
        }
        return mapping.get(stripe_status, PaymentStatus.PENDING)

    async def handle_checkout_webhook(
        self,
        event: stripe.Event
    ) -> Optional[Dict[str, Any]]:
        """Обработать checkout.session webhook

        Args:
            event: Событие Stripe

        Returns:
            Словарь с данными для обновления платежа или None
        """
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']

            return {
                'provider_id': session['id'],
                'status': self.map_stripe_status_to_payment_status(session.get('payment_status', 'pending')),
                'metadata': session.get('metadata', {}),
                'amount': session.get('amount_total', 0) / 100,  # Из центов
                'currency': session.get('currency', 'usd').upper(),
            }

        elif event['type'] == 'checkout.session.async_payment_succeeded':
            session = event['data']['object']
            return {
                'provider_id': session['id'],
                'status': PaymentStatus.PAID,
                'metadata': session.get('metadata', {}),
            }

        elif event['type'] == 'checkout.session.async_payment_failed':
            session = event['data']['object']
            return {
                'provider_id': session['id'],
                'status': PaymentStatus.FAILED,
                'metadata': session.get('metadata', {}),
            }

        return None


# Глобальный экземпляр клиента
stripe_client = None


def init_stripe_client():
    """Инициализация глобального Stripe клиента"""
    global stripe_client
    try:
        stripe_client = StripeClient()
        logger.info("Stripe клиент инициализирован")
        return True
    except Exception as e:
        logger.warning(f"Stripe клиент не инициализирован: {e}")
        return False
