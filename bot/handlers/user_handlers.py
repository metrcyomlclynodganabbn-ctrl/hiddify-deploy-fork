"""
User handlers for Hiddify Bot.
Contains all user-facing command and callback handlers.
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database import crud
from database.models import User
from bot.keyboards.user_keyboards import (
    get_user_main_keyboard,
    get_admin_main_keyboard,
)

logger = logging.getLogger(__name__)

# Create router for user handlers
user_router = Router()


@user_router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, user: User):
    """
    Handle /start command with invite codes and referrals.

    Supports:
    - /start — regular start
    - /start INV_XXXXXX — invite code registration
    - /start ref_{user_id} — referral link
    """
    telegram_id = message.from_user.id
    args = message.text.split()

    # Parse start parameters
    invite_code = None
    ref_referrer_id = None

    if len(args) > 1:
        start_param = args[1]
        if start_param.startswith('INV_'):
            # Invite code (v3.x legacy)
            invite_code = start_param
            logger.info(f"User {telegram_id} started with invite code: {invite_code}")
        elif start_param.startswith('ref_'):
            # Referral code (v4.0)
            try:
                ref_referrer_id = int(start_param.split('_')[1])
                logger.info(f"User {telegram_id} started with referral from {ref_referrer_id}")
            except (ValueError, IndexError):
                logger.warning(f"Invalid referral format: {start_param}")

    # Check if user is admin
    is_admin = telegram_id in settings.admin_ids or user.role in ["admin", "manager"]

    # Admin panel
    if is_admin:
        await message.answer(
            f"👑 <b>Панель администратора</b>\n\n"
            f"Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_admin_main_keyboard()
        )
        logger.info(f"Admin {telegram_id} accessed admin panel")
        return

    # Check if user is blocked
    if user.is_blocked:
        await message.answer(
            "⛔ <b>Ваш доступ заблокирован</b>\n\n"
            "Обратитесь к администратору для уточнения деталей.",
            parse_mode="HTML"
        )
        return

    # Check subscription expiry
    if user.expires_at and user.expires_at < datetime.now():
        await message.answer(
            "⚠️ <b>Ваша подписка истекла</b>\n\n"
            "Обратитесь к администратору для продления.",
            parse_mode="HTML"
        )
        return

    # Handle invite code registration
    if invite_code:
        await _handle_invite_code_registration(message, session, user, invite_code)
        return

    # Handle referral link
    if ref_referrer_id:
        await _handle_referral_link(message, session, user, ref_referrer_id)
        return

    # Regular start - show welcome message
    await message.answer(
        f"🛡️ <b>{message.from_user.first_name or 'Пользователь'}</b>\n\n"
        f"Добро пожаловать! Ваш статус: ✅ Активен",
        parse_mode="HTML",
        reply_markup=get_user_main_keyboard(
            has_subscription=bool(user.expires_at and user.expires_at > datetime.now()),
            trial_available=not user.trial_activated,
            show_referral=True,
        )
    )

    logger.info(f"User {telegram_id} ({user.telegram_username}) called /start")


async def _handle_invite_code_registration(
    message: Message,
    session: AsyncSession,
    user: User,
    invite_code: str
):
    """Handle registration via invite code."""
    telegram_id = message.from_user.id

    # Validate invite code
    invite = await crud.validate_invite_code(session, invite_code)

    if not invite:
        await message.answer(
            "❌ <b>Неверный инвайт-код</b>\n\n"
            "Ссылка недействительна или истекла. "
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        return

    # Use invite code
    result = await crud.use_invite_code(session, invite_code)

    if result['success']:
        await message.answer(
            "✅ <b>Добро пожаловать!</b>\n\n"
            "Ваш доступ активирован. "
            "Теперь вы можете пользоваться VPN.",
            parse_mode="HTML",
            reply_markup=get_user_main_keyboard(
                has_subscription=True,
                trial_available=False,
                show_referral=True,
            )
        )
        logger.info(f"User {telegram_id} registered via invite code: {invite_code}")
    else:
        await message.answer(
            f"❌ {result['message']}",
            parse_mode="HTML"
        )


async def _handle_referral_link(
    message: Message,
    session: AsyncSession,
    user: User,
    ref_referrer_id: int
):
    """Handle registration via referral link."""
    telegram_id = message.from_user.id

    # Create referral record
    try:
        referral = await crud.create_referral(
            session=session,
            referrer_id=ref_referrer_id,
            referred_id=telegram_id,
            bonus_amount=settings.referral_bonus,
        )
        await session.commit()

        await message.answer(
            "✅ <b>Добро пожаловать!</b>\n\n"
            "Ваш доступ активирован. "
            "Теперь вы можете пользоваться VPN.",
            parse_mode="HTML",
            reply_markup=get_user_main_keyboard(
                has_subscription=True,
                trial_available=False,
                show_referral=True,
            )
        )
        logger.info(
            f"Referral created: {ref_referrer_id} -> {telegram_id}, "
            f"bonus: ${settings.referral_bonus}"
        )
    except Exception as e:
        logger.error(f"Failed to create referral: {e}")
        await message.answer(
            "❌ Ошибка активации. Обратитесь к админу."
        )


@user_router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "Доступные команды:\n"
        "/start — Главное меню\n"
        "/help — Эта справка\n"
        "/cancel — Отменить операцию\n"
        "/profile — Мой профиль\n\n"
        "🔧 Бот в разработке...",
        parse_mode="HTML"
    )


@user_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state):
    """Handle /cancel command."""
    # Clear any FSM state
    await state.clear()

    await message.answer("❌ Операция отменена")


@user_router.message(Command("profile"))
async def cmd_profile(message: Message, user: User):
    """Handle /profile command."""
    from datetime import datetime

    # Calculate subscription status
    status = "✅ Активен"
    if user.expires_at:
        if user.expires_at < datetime.now():
            status = "⚠️ Истекла"
        else:
            days_left = (user.expires_at - datetime.now()).days
            status = f"✅ Активен ({days_left} дн. осталось)"

    # Calculate usage
    usage_percent = (user.used_bytes / user.data_limit_bytes) * 100 if user.data_limit_bytes else 0

    await message.answer(
        f"👤 <b>Профиль пользователя</b>\n\n"
        f"🔗 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"👤 Username: @{user.telegram_username or 'не задан'}\n"
        f"📊 Статус: {status}\n"
        f"💾 Использовано: {usage_percent:.1f}% ({user.used_bytes / (1024**3):.2f} GB из {user.data_limit_bytes / (1024**3):.2f} GB)\n"
        f"📅 Истекает: {user.expires_at.strftime('%Y-%m-%d %H:%M') if user.expires_at else 'Не ограничено'}\n\n"
        f"🔑 Протокол: VLESS Reality ({'✅' if user.vless_enabled else '☐'})",
        parse_mode="HTML"
    )
