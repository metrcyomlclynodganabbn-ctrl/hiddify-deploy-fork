"""
User handlers for Hiddify Bot.
Contains all user-facing command and callback handlers.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database import crud
from database.models import User
from bot.states.user_states import (
    GetKeyStates,
    TrialStates,
    TicketStates,
    ReferralStates,
)
from bot.keyboards.user_keyboards import (
    get_user_main_keyboard,
    get_admin_main_keyboard,
    get_protocol_inline_keyboard,
    get_platform_inline_keyboard,
    get_trial_inline_keyboard,
    get_buy_subscription_inline_keyboard,
    get_support_categories_keyboard,
    get_referral_inline_keyboard,
    get_confirm_cancel_inline_keyboard,
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
    if user.expires_at and user.expires_at < datetime.now(timezone.utc):
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
            has_subscription=bool(user.expires_at and user.expires_at > datetime.now(timezone.utc)),
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
    # Calculate subscription status
    status = "✅ Активен"
    if user.expires_at:
        if user.expires_at < datetime.now(timezone.utc):
            status = "⚠️ Истекла"
        else:
            days_left = (user.expires_at - datetime.now(timezone.utc)).days
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


# ============================================================================
# ЭТАП 5.2: Other user handlers
# ============================================================================

# ----------------------------------------------------------------------------
# "Мои устройства" handler
# ----------------------------------------------------------------------------

@user_router.message(F.text == "📱 Мои устройства")
async def handle_my_devices(message: Message, user: User, session: AsyncSession):
    """Handle 'Мои устройства' button - show active connections."""
    telegram_id = message.from_user.id

    try:
        # Import hiddify client
        from services.hiddify_client import get_hiddify_client

        hiddify = get_hiddify_client()
        connections = await hiddify.get_user_connections(user.vless_uuid)
    except Exception as e:
        logger.warning(f"Failed to get user connections: {e}")
        connections = None

    if connections:
        response = "📱 <b>Мои устройства</b>\n\nАктивные подключения:\n\n"
        for conn in connections[:10]:  # Максимум 10 подключений
            device = conn.get('device', 'Неизвестное устройство')
            location = conn.get('location', 'N/A')
            connected_at = conn.get('connected_at', 'N/A')
            protocol = conn.get('protocol', 'N/A')

            response += (
                f"┌────────────────────────────┐\n"
                f"│ 📱 <b>{device}</b>\n"
                f"│ 🌍 {location}\n"
                f"│ 🔗 {protocol}\n"
                f"│ ⏰ {connected_at}\n"
                f"└────────────────────────────┘\n\n"
            )
    else:
        # Заглушка если API недоступен
        response = (
            "📱 <b>Мои устройства</b>\n\n"
            "Активные подключения:\n\n"
            "Нет данных о подключениях\n\n"
            "<i>(API интеграция в процессе настройки)</i>"
        )

    await message.answer(response, parse_mode="HTML")
    await crud.update_user_activity(session, user)
    await session.commit()


# ----------------------------------------------------------------------------
# "Получить ключ" handler
# ----------------------------------------------------------------------------

@user_router.message(F.text == "🔗 Получить ключ")
async def handle_get_key(message: Message, user: User):
    """Handle 'Получить ключ' button - show protocol selection."""
    await message.answer(
        "📱 <b>Выберите протокол</b>\n\n"
        "VLESS Reality обеспечивает максимальную скорость "
        "и стабильность соединения.",
        parse_mode="HTML",
        reply_markup=get_protocol_inline_keyboard()
    )


@user_router.callback_query(F.data == "protocol_vless_reality")
async def callback_protocol_vless_reality(callback: CallbackQuery, state):
    """Handle VLESS Reality protocol selection."""
    await callback.message.edit_text(
        "📱 <b>Выберите платформу</b>\n\n"
        "Выберите вашу операционную систему:",
        parse_mode="HTML",
        reply_markup=get_platform_inline_keyboard()
    )
    await state.set_state(GetKeyStates.select_platform)
    await callback.answer()


@user_router.callback_query(GetKeyStates.select_platform, F.data.startswith("platform_"))
async def callback_platform_selected(callback: CallbackQuery, state, user: User):
    """Handle platform selection and generate config."""
    platform = callback.data.split("_")[1]

    platform_names = {
        "ios": "iOS",
        "android": "Android",
        "windows": "Windows",
        "macos": "macOS",
        "linux": "Linux",
        "web": "Web",
    }

    platform_name = platform_names.get(platform, platform)

    # TODO: Generate VLESS Reality config
    # from services.hiddify_client import get_hiddify_client
    # hiddify = get_hiddify_client()
    # config_url = await hiddify.get_subscription_link(user.vless_uuid)

    # Временно - демо сообщение
    config_url = f"vless://[uuid]@[server]:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=[sni]&fp=chrome&pbk=[pbk]&sid=[sid]#Hiddify"

    text = f"🔑 <b>VLESS Reality — {platform_name}</b>\n\n"
    text += f"<code>{config_url}</code>\n\n"
    text += "<b>Инструкция по установке:</b>\n\n"

    instructions = {
        "ios": "1. Установите Safari/Foxray\n2. Откройте ссылку выше\n3. Импортируйте конфиг",
        "android": "1. Установите v2rayNG\n2. Нажмите '+' → 'Импорт из буфера'\n3. Вставьте ссылку",
        "windows": "1. Установите v2rayN\n2. Откройте сервер → 'Импорт из буфера'\n3. Вставьте ссылку",
        "macos": "1. Установите Qv2ray/ClashX\n2. Импортируйте конфиг",
        "linux": "1. Установите qv2ray/v2rayA\n2. Импортируйте конфиг",
        "web": "Используйте браузерное расширение",
    }

    text += instructions.get(platform, "Инструкция в процессе подготовки...")

    # TODO: Generate QR code
    # from utils.qr_generator import generate_qr_code
    # qr_buffer = generate_qr_code(config_url)
    # await callback.message.answer_photo(photo=qr_buffer, caption=text, parse_mode="HTML")

    await callback.message.edit_text(text, parse_mode="HTML")
    await state.clear()
    await callback.answer()


# ----------------------------------------------------------------------------
# "Моя подписка" handler
# ----------------------------------------------------------------------------

@user_router.message(F.text == "📊 Моя подписка")
async def handle_my_subscription(message: Message, user: User, session: AsyncSession):
    """Handle 'Моя подписка' button - show subscription status."""
    telegram_id = message.from_user.id

    # Check if user has active subscription
    has_subscription = user.expires_at and user.expires_at > datetime.now(timezone.utc)

    if not has_subscription:
        # No active subscription - show trial or buy options
        if not user.trial_activated:
            await message.answer(
                "📊 <b>Моя подписка</b>\n\n"
                "У вас нет активной подписки.\n\n"
                "🎁 Доступен пробный период на 7 дней!",
                parse_mode="HTML",
                reply_markup=get_trial_inline_keyboard()
            )
        else:
            await message.answer(
                "📊 <b>Моя подписка</b>\n\n"
                "У вас нет активной подписки.\n\n"
                "Оформите подписку для продолжения использования:",
                parse_mode="HTML",
                reply_markup=get_buy_subscription_inline_keyboard()
            )
        await crud.update_user_activity(session, user)
        await session.commit()
        return

    # Calculate days left
    days_left = (user.expires_at - datetime.now(timezone.utc)).days

    # Calculate usage
    used_gb = user.used_bytes / (1024**3)
    limit_gb = user.data_limit_bytes / (1024**3) if user.data_limit_bytes else 0
    used_percent = (used_gb / limit_gb * 100) if limit_gb > 0 else 0

    subscription_type = "Пробный период" if user.is_trial else "Приватный"

    response = (
        f"📊 <b>Моя подписка</b>\n\n"
        f"Статус: ✅ Активен\n\n"
        f"Тип: {subscription_type}\n"
        f"Истекает: {user.expires_at.strftime('%d.%m.%Y %H:%M')} (осталось {days_left} дней)\n\n"
        f"Лимит трафика:\n"
        f"{used_percent:.1f}% - {used_gb:.1f} GB / {limit_gb:.0f} GB"
    )

    await message.answer(response, parse_mode="HTML")
    await crud.update_user_activity(session, user)
    await session.commit()


@user_router.callback_query(F.data == "activate_trial")
async def callback_activate_trial(callback: CallbackQuery, state):
    """Handle trial activation request."""
    await callback.message.edit_text(
        "🎁 <b>Активация пробного периода</b>\n\n"
        "Пробный период на 7 дней с лимитом 5 GB.\n\n"
        "Активировать?",
        parse_mode="HTML",
        reply_markup=get_confirm_cancel_inline_keyboard()
    )
    await state.set_state(TrialStates.confirming)
    await callback.answer()


@user_router.callback_query(TrialStates.confirming, F.data == "confirm_operation")
async def callback_trial_confirmed(callback: CallbackQuery, state, user: User, session: AsyncSession):
    """Handle confirmed trial activation."""
    # Check if trial already activated
    if user.trial_activated:
        await callback.message.edit_text(
            "⚠️ Пробный период уже был активирован.",
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        return

    # Activate trial
    trial_days = 7
    trial_limit_gb = 5

    user.trial_activated = True
    user.is_trial = True
    user.expires_at = datetime.now(timezone.utc) + timedelta(days=trial_days)
    user.data_limit_bytes = trial_limit_gb * 1024**3
    user.used_bytes = 0

    await session.commit()

    await callback.message.edit_text(
        f"🎉 <b>Пробный период активирован!</b>\n\n"
        f"📅 Длительность: {trial_days} дней\n"
        f"📊 Лимит трафика: {trial_limit_gb} GB\n\n"
        f"⏰ Истекает: {user.expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Нажмите 'Получить ключ' для подключения!",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("Пробный период активирован")


# ----------------------------------------------------------------------------
# "Поддержка" handler
# ----------------------------------------------------------------------------

@user_router.message(F.text == "💬 Поддержка")
async def handle_support(message: Message):
    """Handle 'Поддержка' button - show ticket categories."""
    await message.answer(
        "📝 <b>Выберите категорию обращения</b>\n\n"
        "Опишите вашу проблему, и мы ответим в ближайшее время.",
        parse_mode="HTML",
        reply_markup=get_support_categories_keyboard()
    )


@user_router.callback_query(F.data.startswith("ticket_category_"))
async def callback_ticket_category(callback: CallbackQuery, state):
    """Handle ticket category selection."""
    category = callback.data.replace("ticket_category_", "")

    category_names = {
        "payment": "💳 Оплата",
        "connection": "🔗 Подключение",
        "speed": "📶 Скорость",
        "account": "👤 Аккаунт",
        "other": "📝 Другое",
    }

    await callback.message.edit_text(
        f"📝 Категория: {category_names.get(category, category)}\n\n"
        "Введите краткое описание проблемы (заголовок):",
        parse_mode="HTML"
    )
    await state.update_data(category=category)
    await state.set_state(TicketStates.enter_title)
    await callback.answer()


@user_router.message(TicketStates.enter_title)
async def message_ticket_title(message: Message, state):
    """Handle ticket title input."""
    title = message.text.strip()

    if len(title) < 3 or len(title) > 200:
        await message.answer(
            "❌ Заголовок должен быть от 3 до 200 символов. Попробуйте ещё раз:"
        )
        return

    await state.update_data(title=title)

    await message.answer(
        "✅ Заголовок принят.\n\n"
        "Теперь введите подробное описание проблемы:"
    )
    await state.set_state(TicketStates.enter_description)


@user_router.message(TicketStates.enter_description)
async def message_ticket_description(message: Message, state, user: User, session: AsyncSession):
    """Handle ticket description input and create ticket."""
    description = message.text.strip()

    if len(description) < 10 or len(description) > 5000:
        await message.answer(
            "❌ Описание должно быть от 10 до 5000 символов. Попробуйте ещё раз:"
        )
        return

    data = await state.get_data()
    category = data.get('category', 'other')
    title = data.get('title', 'Без заголовка')

    # Create ticket
    ticket = await crud.create_support_ticket(
        session=session,
        user_id=user.telegram_id,
        category=category,
        priority="normal",
        title=title,
        description=description,
    )
    await session.commit()

    await state.clear()

    category_names = {
        "payment": "💳 Оплата",
        "connection": "🔗 Подключение",
        "speed": "📶 Скорость",
        "account": "👤 Аккаунт",
        "other": "📝 Другое",
    }

    await message.answer(
        f"✅ <b>Тикет создан!</b>\n\n"
        f"Категория: {category_names.get(category, category)}\n"
        f"Заголовок: {title}\n"
        f"Номер тикета: #{ticket.id}\n\n"
        "Мы ответим вам в ближайшее время.",
        parse_mode="HTML"
    )

    await crud.update_user_activity(session, user)
    await session.commit()


# ----------------------------------------------------------------------------
# "Пригласить друга" handler
# ----------------------------------------------------------------------------

@user_router.message(F.text == "👥 Пригласить друга")
async def handle_invite_friend(message: Message, user: User, session: AsyncSession):
    """Handle 'Пригласить друга' button - show referral link and stats."""
    telegram_id = message.from_user.id

    # Get referral stats
    stats = await crud.get_referral_stats(session, telegram_id)

    referral_link = (
        f"https://t.me/{settings.bot_username}?start=ref_{telegram_id}"
    )

    response = (
        f"👥 <b>Пригласить друга</b>\n\n"
        f"Пригласили: <b>{stats['total_referrals']}</b> человек\n"
        f"Активных: <b>{stats['active_referrals']}</b>\n"
        f"Заработано: <b>${stats['total_earned']:.2f}</b>\n\n"
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{referral_link}</code>"
    )

    await message.answer(
        response,
        parse_mode="HTML",
        reply_markup=get_referral_inline_keyboard()
    )

    await crud.update_user_activity(session, user)
    await session.commit()


@user_router.callback_query(F.data == "invite_copy")
async def callback_invite_copy(callback: CallbackQuery, user: User):
    """Handle copy referral link."""
    referral_link = (
        f"https://t.me/{settings.bot_username}?start=ref_{user.telegram_id}"
    )

    await callback.answer(
        f"📋 Ссылка скопирована!\n{referral_link}",
        show_alert=True
    )


# ----------------------------------------------------------------------------
# Cancel operation handler
# ----------------------------------------------------------------------------

@user_router.callback_query(F.data == "cancel_operation")
async def callback_cancel_operation(callback: CallbackQuery, state):
    """Handle cancel operation callback."""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Операция отменена")


# ----------------------------------------------------------------------------
# Import missing keyboard for trial confirmation
# ----------------------------------------------------------------------------
