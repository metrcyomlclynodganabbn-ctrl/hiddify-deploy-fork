"""
Payment handlers for Hiddify Bot.
CryptoBot integration (USDT/TON) with invoice creation and webhook handling.
"""

import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, SuccessfulPayment
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.settings import settings
from database import crud
from database.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    User,
    Subscription,
)
from bot.states.user_states import PaymentStates
from bot.keyboards.user_keyboards import (
    get_subscription_plans_keyboard,
    get_payment_methods_keyboard,
    get_cancel_inline_keyboard,
)

logger = logging.getLogger(__name__)

# Create router for payment handlers
payment_router = Router()

# Subscription plans
SUBSCRIPTION_PLANS = {
    "weekly": {
        "code": "weekly",
        "name": "Неделя",
        "description": "Доступ на 7 дней",
        "price_usd": 3.00,
        "price_stars": 200,  # ~$3.00 @ 1 Star ≈ $0.015
        "duration_days": 7,
        "data_limit_gb": 10,
        "features": ["До 10 GB трафика", "7 дней доступа", "Standard скорость"],
    },
    "monthly": {
        "code": "monthly",
        "name": "Месяц",
        "description": "Доступ на 30 дней",
        "price_usd": 10.00,
        "price_stars": 700,  # ~$10.50 @ 1 Star ≈ $0.015
        "duration_days": 30,
        "data_limit_gb": 50,
        "features": ["До 50 GB трафика", "30 дней доступа", "Высокая скорость"],
    },
    "quarterly": {
        "code": "quarterly",
        "name": "Квартал",
        "description": "Доступ на 90 дней",
        "price_usd": 25.00,
        "price_stars": 1700,  # ~$25.50 @ 1 Star ≈ $0.015
        "duration_days": 90,
        "data_limit_gb": 200,
        "features": ["До 200 GB трафика", "90 дней доступа", "Приоритетная поддержка"],
    },
}


# ============================================================================
# BUY SUBSCRIPTION FLOW
# ============================================================================

@payment_router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: CallbackQuery, state):
    """Start buy subscription flow - show plans."""
    await state.clear()

    text = "💳 <b>Выберите план подписки</b>\n\n"

    for plan_key, plan in SUBSCRIPTION_PLANS.items():
        text += f"• <b>{plan['name']}</b> — ${plan['price_usd']:.2f}\n"
        text += f"  {plan['description']}\n"
        for feature in plan['features']:
            text += f"  ✓ {feature}\n"
        text += "\n"

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_subscription_plans_keyboard()
    )
    await callback.answer()


@payment_router.callback_query(F.data.startswith("plan_"))
async def callback_plan_selected(callback: CallbackQuery, state):
    """Handle plan selection - show payment methods."""
    plan_key = callback.data.split("_")[1]
    plan = SUBSCRIPTION_PLANS.get(plan_key)

    if not plan:
        await callback.answer("❌ План не найден")
        return

    # Save plan to state
    await state.update_data(
        plan_key=plan_key,
        plan_code=plan['code'],
        plan_name=plan['name'],
        price_usd=plan['price_usd'],
        duration_days=plan['duration_days'],
        data_limit_gb=plan['data_limit_gb'],
    )

    await callback.message.edit_text(
        f"💳 <b>Выбран план: {plan['name']}</b>\n"
        f"Сумма: ${plan['price_usd']:.2f}\n\n"
        "Выберите способ оплаты:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_payment_methods_keyboard()
    )
    await callback.answer()


# ============================================================================
# CRYPTOBOT PAYMENTS
# ============================================================================

@payment_router.callback_query(F.data == "pay_cryptobot")
async def callback_pay_cryptobot(callback: CallbackQuery, state, session: AsyncSession, user: User):
    """Handle CryptoBot payment selection - create invoice."""
    if not settings.cryptobot_api_token:
        await callback.message.edit_text(
            "❌ <b>CryptoBot не настроен</b>\n\n"
            "Свяжитесь с администратором.",
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        return

    data = await state.get_data()
    plan_key = data.get('plan_key')
    plan = SUBSCRIPTION_PLANS.get(plan_key)

    if not plan:
        await callback.answer("❌ План не найден")
        return

    # Check if user has pending payment
    existing_payment = await session.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .where(Payment.provider == PaymentProvider.CRYPTOBOT)
        .where(Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    existing_payment = existing_payment.scalar_one_or_none()

    # Create payment record
    payment = await crud.create_payment(
        session=session,
        user_id=user.id,
        provider=PaymentProvider.CRYPTOBOT,
        provider_payment_id="",  # Will be filled after invoice creation
        amount=Decimal(str(plan['price_usd'])),
        currency="USD",
        plan_code=plan['code'],
        duration_days=plan['duration_days'],
        data_limit_gb=plan['data_limit_gb'],
    )
    await session.commit()
    await session.refresh(payment)

    try:
        # Create CryptoBot invoice
        import httpx

        # CryptoBot API endpoint
        api_url = "https://pay.crypt.bot/api/createInvoice"

        # Build invoice parameters
        params = {
            "api_token": settings.cryptobot_api_token,
            "asset": "USDT",
            "amount": plan['price_usd'],
            "description": f"Подписка {plan['name']} - @{user.telegram_username or user.telegram_id}",
            "hidden_message": f"Спасибо за оплату! Подписка {plan['name']} активирована.",
            "payload": str(payment.id),  # Use our payment ID as payload
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600,  # 1 hour
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, params=params, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        if result.get("ok"):
            invoice_data = result["result"]
            bot_invoice_id = invoice_data["invoice_id"]
            pay_url = invoice_data["pay_url"]
            mini_app_url = invoice_data["mini_app_url"]

            # Update payment with provider payment ID
            payment.provider_payment_id = str(bot_invoice_id)
            await session.commit()
            await session.refresh(payment)

            # Send invoice to user
            await callback.message.edit_text(
                f"💳 <b>Оплата через CryptoBot</b>\n\n"
                f"План: {plan['name']}\n"
                f"Сумма: ${plan['price_usd']:.2f} USDT\n\n"
                f"Нажмите кнопку ниже для оплаты:",
                parse_mode=ParseMode.HTML,
                reply_markup=_get_cryptobot_invoice_keyboard(pay_url, mini_app_url, payment.id)
            )

            logger.info(
                f"CryptoBot invoice created: payment_id={payment.id}, "
                f"bot_invoice_id={bot_invoice_id}, user={user.telegram_id}"
            )
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"CryptoBot invoice creation failed: {error_msg}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка создания инвойса</b>\n\n"
                f"{error_msg}\n\n"
                f"Попробуйте позже или обратитесь к администратору.",
                parse_mode=ParseMode.HTML
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"CryptoBot invoice error: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка создания платежа</b>\n\n"
            "Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )
        await callback.answer()


def _get_cryptobot_invoice_keyboard(pay_url: str, mini_app_url: str, payment_id: int):
    """Create inline keyboard for CryptoBot invoice."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Оплатить USDT", url=pay_url)
    )
    builder.row(
        InlineKeyboardButton(text="📱 CryptoBot App", url=mini_app_url)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_payment_{payment_id}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="buy_subscription")
    )

    return builder.as_markup()


@payment_router.callback_query(F.data.startswith("check_payment_"))
async def callback_check_payment(callback: CallbackQuery, session: AsyncSession, user: User):
    """Check payment status manually."""
    payment_id = int(callback.data.split("_")[2])

    payment = await session.get(Payment, payment_id)
    if not payment or payment.user_id != user.id:
        await callback.answer("❌ Платёж не найден")
        return

    if payment.status == PaymentStatus.COMPLETED:
        await callback.answer("✅ Платёж уже оплачен!")
        return

    if payment.status == PaymentStatus.PENDING:
        # Check status with CryptoBot
        try:
            import httpx

            api_url = "https://pay.crypt.bot/api/getInvoices"
            params = {
                "api_token": settings.cryptobot_api_token,
                "invoice_id": payment.provider_payment_id,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, params=params, timeout=30.0)
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                invoices = result["result"]
                if invoices:
                    invoice = invoices[0]
                    status = invoice.get("status")

                    if status == "paid":
                        # Process successful payment
                        payment.status = PaymentStatus.COMPLETED
                        payment.completed_at = datetime.now()
                        await session.commit()

                        # Activate subscription
                        await _activate_subscription(session, user, payment)

                        await callback.message.edit_text(
                            "✅ <b>Оплата прошла успешно!</b>\n\n"
                            f"Подписка активирована.\n"
                            f"Нажмите 'Получить ключ' для подключения.",
                            parse_mode=ParseMode.HTML
                        )
                        await callback.answer("✅ Оплата подтверждена!")
                        return
                    elif status == "expired":
                        payment.status = PaymentStatus.EXPIRED
                        await session.commit()
                        await callback.answer("⏰ Срок инвойса истёк")
                        return

            await callback.answer("⏳ Ожидание оплаты...")
            return

        except Exception as e:
            logger.error(f"Payment check error: {e}")
            await callback.answer("❌ Ошибка проверки")
            return

    await callback.answer("ℹ️ Платёж не найден")


async def _activate_subscription(session: AsyncSession, user: User, payment: Payment):
    """Activate subscription after successful payment."""
    # Calculate new expiry date
    base_date = user.expires_at if user.expires_at and user.expires_at > datetime.now() else datetime.now()
    new_expiry = base_date + timedelta(days=payment.duration_days)

    # Update user
    user.expires_at = new_expiry
    user.is_trial = False

    # Update data limit if specified
    if payment.data_limit_gb:
        user.data_limit_bytes = payment.data_limit_gb * 1024**3
        user.used_bytes = 0

    await session.commit()
    logger.info(
        f"Subscription activated: user={user.telegram_id}, "
        f"plan={payment.plan_code}, expires={new_expiry}"
    )


# ============================================================================
# WEBHOOK HANDLER (for external webhooks)
# ============================================================================

async def process_cryptobot_webhook(payload: dict, signature: str) -> dict:
    """
    Process CryptoBot webhook.
    Called from main.py webhook endpoint.

    Args:
        payload: Webhook payload from CryptoBot
        signature: HMAC SHA256 signature

    Returns:
        dict with status
    """
    # Verify signature
    if not settings.cryptobot_api_token:
        return {"ok": False, "error": "CryptoBot not configured"}

    # Check signature
    expected_signature = hmac.new(
        settings.cryptobot_api_token.encode(),
        str(payload).encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        logger.warning("Invalid CryptoBot webhook signature")
        return {"ok": False, "error": "Invalid signature"}

    # Process webhook
    try:
        from database.base import get_async_session

        async for session in get_async_session():
            # Extract data
            invoice_id = payload.get("invoice_id")
            status = payload.get("status")  # "paid", "expired", etc.
            payload_data = payload.get("payload")  # Our payment ID

            if not payload_data:
                return {"ok": False, "error": "No payload"}

            payment_id = int(payload_data)

            # Find payment
            payment = await session.get(Payment, payment_id)
            if not payment:
                return {"ok": False, "error": "Payment not found"}

            # Update payment status
            if status == "paid" and payment.status == PaymentStatus.PENDING:
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.now()

                # Get user and activate subscription
                user = await session.get(User, payment.user_id)
                if user:
                    await _activate_subscription(session, user, payment)

                await session.commit()
                logger.info(f"Payment completed via webhook: payment_id={payment_id}")

                return {"ok": True}

            elif status == "expired" and payment.status == PaymentStatus.PENDING:
                payment.status = PaymentStatus.EXPIRED
                await session.commit()
                logger.info(f"Payment expired via webhook: payment_id={payment_id}")

                return {"ok": True}

            return {"ok": False, "error": "Status not processed"}

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================================
# PROMO CODES
# ============================================================================

@payment_router.callback_query(F.data == "pay_promo")
async def callback_pay_promo(callback: CallbackQuery, state):
    """Handle promo code selection."""
    await callback.message.edit_text(
        "🎫 <b>Введите промокод</b>\n\n"
        "Промокод дает скидку на покупку подписки.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_inline_keyboard()
    )
    await state.set_state(PaymentStates.entering_promo)
    await callback.answer()


@payment_router.message(PaymentStates.entering_promo)
async def message_promo_code(message: Message, state, session: AsyncSession):
    """Handle promo code input."""
    # TODO: Implement promo code validation and discount application
    await message.answer(
        "🎫 <b>Промокоды</b>\n\n"
        "Функционал в разработке.\n\n"
        "Свяжитесь с администратором для получения промокода.",
        parse_mode=ParseMode.HTML
    )
    await state.clear()


# ============================================================================
# CANCEL PAYMENT
# ============================================================================

@payment_router.callback_query(F.data == "cancel_payment")
async def callback_cancel_payment(callback: CallbackQuery, state):
    """Handle payment cancellation."""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Оплата отменена")


# ============================================================================
# TELEGRAM STARS PAYMENTS
# ============================================================================

@payment_router.callback_query(F.data == "pay_stars")
async def callback_pay_stars(callback: CallbackQuery, state, session: AsyncSession, user: User):
    """Handle Telegram Stars payment - send invoice."""
    data = await state.get_data()
    plan_key = data.get('plan_key')
    plan = SUBSCRIPTION_PLANS.get(plan_key)

    if not plan:
        await callback.answer("❌ План не найден")
        return

    # Check for pending payments
    existing_payment = await session.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .where(Payment.provider == PaymentProvider.TELEGRAM_STARS)
        .where(Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    existing_payment = existing_payment.scalar_one_or_none()

    # Create payment record
    payment = await crud.create_payment(
        session=session,
        user_id=user.id,
        provider=PaymentProvider.TELEGRAM_STARS,
        provider_payment_id="",  # Will be filled after invoice
        amount=Decimal(str(plan['price_stars'])),
        currency="XTR",
        plan_code=plan['code'],
        duration_days=plan['duration_days'],
        data_limit_gb=plan['data_limit_gb'],
    )
    await session.commit()
    await session.refresh(payment)

    # Generate unique invoice ID
    invoice_id = f"stars_{payment.id}_{user.telegram_id}"

    try:
        # Send invoice via Telegram Stars API
        await callback.message.answer_invoice(
            title=f"Подписка: {plan['name']}",
            description=plan['description'],
            payload=str(payment.id),  # Use our payment ID as payload
            provider_token="",  # Empty for Telegram Stars
            currency="XTR",
            prices=[{
                "label": f"{plan['name']} ({plan['duration_days']} дней)",
                "amount": plan['price_stars'],
            }],
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False,
        )

        # Update payment with provider payment ID
        payment.provider_payment_id = invoice_id
        await session.commit()

        await callback.message.delete()
        await callback.answer("✅ Инвойс отправлен")

        logger.info(
            f"Telegram Stars invoice created: payment_id={payment.id}, "
            f"invoice_id={invoice_id}, amount={plan['price_stars']} XTR"
        )

    except Exception as e:
        logger.error(f"Telegram Stars invoice error: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка создания платежа</b>\n\n"
            "Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )
        await callback.answer()


@payment_router.pre_checkout_query(F.data.startswith("stars_"))
async def pre_checkout_stars(pre_checkout_query: PreCheckoutQuery, session: AsyncSession):
    """
    Handle pre-checkout query for Telegram Stars.
    Called when user initiates payment.
    """
    try:
        # Get payment ID from payload
        payment_id = int(pre_checkout_query.invoice_payload)

        # Verify payment exists and is pending
        payment = await session.get(Payment, payment_id)
        if not payment or payment.status != PaymentStatus.PENDING:
            await pre_checkout_query.answer(ok=False, error_message="Платёж не найден или истёк")
            return

        # Approve payment
        await pre_checkout_query.answer(ok=True)
        logger.info(f"Pre-checkout approved: payment_id={payment_id}")

    except Exception as e:
        logger.error(f"Pre-checkout error: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка оплаты")


@payment_router.message(F.successful_payment)
async def on_successful_payment(message: Message, successful_payment: SuccessfulPayment, session: AsyncSession):
    """
    Handle successful Telegram Stars payment.
    Called automatically after payment is completed.
    """
    try:
        # Get payment ID from payload
        payment_id = int(successful_payment.invoice_payload)

        payment = await session.get(Payment, payment_id)
        if not payment:
            await message.answer("❌ Платёж не найден")
            return

        # Check if already processed
        if payment.status == PaymentStatus.COMPLETED:
            await message.answer("✅ Этот платёж уже был обработан")
            return

        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.now()

        # Get user and activate subscription
        user = await session.get(User, payment.user_id)
        if user:
            await _activate_subscription(session, user, payment)

        await session.commit()

        await message.answer(
            "✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Подписка активирована.\n"
            f"Нажмите 'Получить ключ' для подключения.",
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Telegram Stars payment completed: payment_id={payment_id}, "
            f"user={user.telegram_id if user else 'unknown'}, "
            f"amount={successful_payment.total_amount} XTR"
        )

    except Exception as e:
        logger.error(f"Successful payment processing error: {e}")
        await message.answer("❌ Ошибка обработки платежа")
