"""
Admin handlers for Hiddify Bot.
Contains all admin-only command and callback handlers.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database import crud
from database.models import User
from bot.states.user_states import (
    CreateUserStates,
    AdminUserStates,
    InviteStates,
)
from bot.keyboards.user_keyboards import (
    get_admin_main_keyboard,
    get_admin_user_inline_keyboard,
    get_invite_management_keyboard,
    get_ticket_actions_keyboard,
    get_cancel_inline_keyboard,
    get_confirm_cancel_inline_keyboard,
)

logger = logging.getLogger(__name__)

# Create router for admin handlers
admin_router = Router()


# ============================================================================
# ADMIN ENTRY POINT
# ============================================================================

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command - show admin panel."""
    telegram_id = message.from_user.id

    # Check if user is admin
    if telegram_id not in settings.admin_ids:
        await message.answer("🚫 У вас нет прав администратора")
        return

    await message.answer(
        "👑 <b>Панель администратора</b>\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )
    logger.info(f"Admin {telegram_id} accessed admin panel")


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@admin_router.message(F.text == "👥 Пользователи")
async def handle_admin_users(message: Message, session: AsyncSession):
    """Handle 'Пользователи' button - show users list."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        return

    users = await crud.get_users_list(session, limit=50, active_only=False)

    if not users:
        await message.answer(
            "👥 <b>Пользователи</b>\n\n"
            "Пользователей нет",
            parse_mode="HTML"
        )
        return

    # Form message with first 20 users
    response = "👥 <b>Пользователи</b> (первые 20 из 50)\n\n"

    for user in users[:20]:
        username = user.telegram_username or user.telegram_first_name or "Без имени"
        status = "✅" if user.is_active else "❌"
        trial = " 🎁" if user.is_trial else ""
        created = user.created_at.strftime("%d.%m.%Y") if user.created_at else "N/A"

        response += f"{status} @{username}{trial}\n"
        response += f"   ID: {user.telegram_id} | {created}\n\n"

    response += f"\nВсего: {len(users)} пользователей"

    # Check message length
    if len(response.encode('utf-8')) > 4096:
        response = f"👥 <b>Пользователи</b>\n\nВсего: {len(users)}\n\nСлишком много для отображения"

    await message.answer(response, parse_mode="HTML")


@admin_router.message(F.text == "➕ Создать юзера")
async def handle_admin_create_user(message: Message, state):
    """Handle 'Создать юзера' button - start user creation flow."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        return

    await message.answer(
        "➕ <b>Создать пользователя</b>\n\n"
        "Шаг 1 из 2: Введите username Telegram\n\n"
        "<i>Пример: @username</i>\n\n"
        "Или перешлите сообщение от пользователя",
        parse_mode="HTML",
        reply_markup=get_cancel_inline_keyboard()
    )
    await state.set_state(CreateUserStates.username)


@admin_router.message(CreateUserStates.username)
async def message_create_user_username(message: Message, state):
    """Handle username input for user creation."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        await state.clear()
        return

    username = message.text.strip()

    # Validate username (with or without @)
    if username.startswith("@"):
        username = username[1:]

    # Handle forwarded message
    if message.forward_from:
        target_user_id = message.forward_from.id
        target_username = message.forward_from.username or f"id{target_user_id}"
    elif username.isdigit():
        target_user_id = int(username)
        target_username = f"id{target_user_id}"
    else:
        target_user_id = None
        target_username = username

    # Save to state
    await state.update_data(
        target_username=target_username,
        target_user_id=target_user_id
    )

    await message.answer(
        f"➕ <b>Подтверждение создания</b>\n\n"
        f"Username: @{target_username}\n\n"
        f"📦 Лимит трафика: 100 GB\n"
        f"📅 Срок действия: 30 дней\n\n"
        f"Создать пользователя?",
        parse_mode="HTML",
        reply_markup=get_confirm_cancel_inline_keyboard()
    )
    await state.set_state(CreateUserStates.confirm)


@admin_router.callback_query(CreateUserStates.confirm, F.data == "confirm_operation")
async def callback_create_user_confirmed(callback: CallbackQuery, state, session: AsyncSession):
    """Handle confirmed user creation."""
    telegram_id = callback.from_user.id
    data = await state.get_data()

    target_username = data.get('target_username', '').lstrip('@')
    target_user_id = data.get('target_user_id')

    # Create user
    try:
        user = await crud.create_user(
            session=session,
            telegram_id=target_user_id or telegram_id,  # Fallback to admin ID for testing
            telegram_username=target_username,
            telegram_first_name=target_username,
            data_limit_bytes=100 * 1024**3,  # 100 GB
            expire_days=30,
        )
        await session.commit()

        await callback.message.edit_text(
            f"✅ <b>Пользователь создан!</b>\n\n"
            f"Username: @{target_username}\n"
            f"UUID: <code>{user.vless_uuid}</code>\n"
            f"Invite: <code>{user.invite_code}</code>",
            parse_mode="HTML"
        )
        logger.info(f"Admin {telegram_id} created user @{target_username}")

    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка создания пользователя: {e}",
            parse_mode="HTML"
        )

    await state.clear()
    await callback.answer()


# ============================================================================
# USER ACTIONS (via inline keyboard)
# ============================================================================

@admin_router.callback_query(F.data.startswith("user_info_"))
async def callback_user_info(callback: CallbackQuery, session: AsyncSession):
    """Show detailed user information."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    target_telegram_id = int(callback.data.split("_")[2])
    user = await crud.get_user_by_telegram_id(session, target_telegram_id)

    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    # Calculate usage
    used_gb = user.used_bytes / (1024**3)
    limit_gb = user.data_limit_bytes / (1024**3) if user.data_limit_bytes else 0
    used_percent = (used_gb / limit_gb * 100) if limit_gb > 0 else 0

    # Days left
    days_left = "∞"
    if user.expires_at:
        days_left = max(0, (user.expires_at - datetime.now(timezone.utc)).days)

    info = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🔗 ID: <code>{user.telegram_id}</code>\n"
        f"👤 Username: @{user.telegram_username or 'не задан'}\n"
        f"📅 Создан: {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else 'N/A'}\n\n"
        f"📊 Статус: {'✅ Активен' if user.is_active else '❌ Неактивен'}\n"
        f"{'🎁 Trial' if user.is_trial else ''}\n"
        f"{'🚫 Заблокирован' if user.is_blocked else ''}\n\n"
        f"💾 Трафик: {used_percent:.1f}% ({used_gb:.1f} GB / {limit_gb:.0f} GB)\n"
        f"⏰ Осталось: {days_left} дней\n\n"
        f"🔑 UUID: <code>{user.vless_uuid}</code>"
    )

    await callback.message.edit_text(
        info,
        parse_mode="HTML",
        reply_markup=get_admin_user_inline_keyboard(user.telegram_id, user.telegram_username)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("user_extend_"))
async def callback_user_extend(callback: CallbackQuery, session: AsyncSession):
    """Extend user subscription."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    target_telegram_id = int(callback.data.split("_")[2])
    user = await crud.get_user_by_telegram_id(session, target_telegram_id)

    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    # Extend by 30 days
    if user.expires_at:
        user.expires_at += timedelta(days=30)
    else:
        user.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    await session.commit()

    new_expire = user.expires_at.strftime("%d.%m.%Y")
    await callback.answer(f"✅ Продлено до {new_expire}")
    logger.info(f"Admin {telegram_id} extended user {target_telegram_id} until {new_expire}")


@admin_router.callback_query(F.data.startswith("user_block_"))
async def callback_user_block(callback: CallbackQuery, session: AsyncSession):
    """Block/unblock user."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    target_telegram_id = int(callback.data.split("_")[2])

    # Get user to find primary key
    user = await crud.get_user_by_telegram_id(session, target_telegram_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    # Block using primary key
    user = await crud.block_user(session, user.id, block=True)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    await session.commit()

    action = "заблокирован" if user.is_blocked else "разблокирован"
    await callback.answer(f"✅ Пользователь {action}")
    logger.info(f"Admin {telegram_id} blocked user {target_telegram_id}")


@admin_router.callback_query(F.data.startswith("user_unblock_"))
async def callback_user_unblock(callback: CallbackQuery, session: AsyncSession):
    """Unblock user."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    target_telegram_id = int(callback.data.split("_")[2])

    # Get user to find primary key
    user = await crud.get_user_by_telegram_id(session, target_telegram_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    # Unblock using primary key
    user = await crud.block_user(session, user.id, block=False)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    await session.commit()

    await callback.answer("✅ Пользователь разблокирован")
    logger.info(f"Admin {telegram_id} unblocked user {target_telegram_id}")


@admin_router.callback_query(F.data.startswith("user_limit_"))
async def callback_user_limit(callback: CallbackQuery, state):
    """Start user limit change flow."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    target_telegram_id = int(callback.data.split("_")[2])

    # Get user primary key for subsequent operations
    user = await crud.get_user_by_telegram_id(session, target_telegram_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    # Save primary key to state
    await state.update_data(user_db_id=user.id)

    await callback.message.edit_text(
        "📦 <b>Изменить лимит трафика</b>\n\n"
        "Введите новый лимит в GB:\n\n"
        "<i>Пример: 50 (для 50 GB)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_inline_keyboard()
    )
    await state.set_state(AdminUserStates.set_limit)
    await callback.answer()


@admin_router.message(AdminUserStates.set_limit)
async def message_user_limit(message: Message, state, session: AsyncSession):
    """Handle new traffic limit input."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        await state.clear()
        return

    try:
        limit_gb = int(message.text.strip())
        if limit_gb < 1 or limit_gb > 1000:
            raise ValueError("Лимит должен быть от 1 до 1000 GB")
    except ValueError as e:
        await message.answer(f"❌ {e}\n\nПопробуйте ещё раз:")
        return

    data = await state.get_data()
    user_db_id = data.get('user_db_id')

    user = await crud.get_user_by_id(session, user_db_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return

    # Update limit
    user.data_limit_bytes = limit_gb * 1024**3
    await session.commit()

    await message.answer(
        f"✅ <b>Лимит обновлён!</b>\n\n"
        f"Новый лимит: {limit_gb} GB",
        parse_mode="HTML"
    )
    logger.info(f"Admin {telegram_id} set user {user_db_id} limit to {limit_gb} GB")
    await state.clear()


@admin_router.callback_query(F.data == "admin_close")
async def callback_admin_close(callback: CallbackQuery):
    """Close admin inline keyboard."""
    await callback.message.delete()
    await callback.answer()


# ============================================================================
# STATISTICS
# ============================================================================

@admin_router.message(F.text == "📈 Статистика")
async def handle_admin_stats(message: Message, session: AsyncSession):
    """Handle 'Статистика' button - show system statistics."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        return

    # Get users stats
    stats = await crud.get_users_stats(session)

    # Try to get Hiddify API stats
    api_stats = {}
    try:
        from services.hiddify_client import get_hiddify_client
        hiddify = get_hiddify_client()
        api_stats = await hiddify.get_stats()
    except Exception as e:
        logger.warning(f"Failed to get API stats: {e}")

    response = (
        "📈 <b>Статистика системы</b>\n\n"
        f"👥 Пользователи:\n"
        f"Всего: {stats['total_users']}\n"
        f"Активных: {stats['active_users']}\n"
        f"Trial: {stats['trial_users']}\n"
        f"Заблокировано: {stats['blocked_users']}\n\n"
    )

    if api_stats:
        today_traffic = api_stats.get('today_traffic', 'N/A')
        month_traffic = api_stats.get('month_traffic', 'N/A')
        response += (
            f"📊 Трафик:\n"
            f"Сегодня: {today_traffic}\n"
            f"Месяц: {month_traffic}\n\n"
        )

    response += f"📅 Дата: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')}"

    await message.answer(response, parse_mode="HTML")


# ============================================================================
# INVITE CODES
# ============================================================================

@admin_router.message(F.text == "🎫 Инвайты")
async def handle_admin_invites(message: Message):
    """Handle 'Инвайты' button - show invite management."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        return

    await message.answer(
        "🎫 <b>Управление инвайтами</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_invite_management_keyboard()
    )


@admin_router.callback_query(F.data == "invite_create")
async def callback_invite_create(callback: CallbackQuery, state):
    """Start invite code creation flow."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    await callback.message.edit_text(
        "🎫 <b>Создать инвайт-код</b>\n\n"
        "Сколько использований допускается?\n\n"
        "<i>Пример: 1 (одноразовый), 10 (на 10 человек)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_inline_keyboard()
    )
    await state.set_state(InviteStates.create_code)
    await callback.answer()


@admin_router.message(InviteStates.create_code)
async def message_invite_max_uses(message: Message, state, session: AsyncSession):
    """Handle max uses input for invite code."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        await state.clear()
        return

    try:
        max_uses = int(message.text.strip())
        if max_uses < 1 or max_uses > 1000:
            raise ValueError("Количество должно быть от 1 до 1000")
    except ValueError as e:
        await message.answer(f"❌ {e}\n\nПопробуйте ещё раз:")
        return

    # Create invite code
    import os
    code = f"INV_{os.urandom(8).hex()}"

    await crud.create_invite_code(
        session=session,
        code=code,
        created_by=telegram_id,
        max_uses=max_uses,
    )
    await session.commit()

    await message.answer(
        f"✅ <b>Инвайт-код создан!</b>\n\n"
        f"Код: <code>{code}</code>\n"
        f"Использований: {max_uses}\n\n"
        f"Ссылка: https://t.me/{settings.bot_username}?start={code}",
        parse_mode="HTML"
    )
    logger.info(f"Admin {telegram_id} created invite code {code} for {max_uses} uses")
    await state.clear()


@admin_router.callback_query(F.data == "invite_list")
async def callback_invite_list(callback: CallbackQuery, session: AsyncSession):
    """Show invite codes list."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    # Get invites (TODO: implement get_invites_list in crud)
    # For now - stub message
    await callback.message.edit_text(
        "🎫 <b>Список инвайт-кодов</b>\n\n"
        "<i>(Функционал в разработке)</i>",
        parse_mode="HTML",
        reply_markup=get_invite_management_keyboard()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "invite_stats")
async def callback_invite_stats(callback: CallbackQuery):
    """Show invite statistics."""
    telegram_id = callback.from_user.id

    if telegram_id not in settings.admin_ids:
        await callback.answer("🚫 Нет прав")
        return

    await callback.message.edit_text(
        "🎫 <b>Статистика инвайтов</b>\n\n"
        "<i>(Функционал в разработке)</i>",
        parse_mode="HTML",
        reply_markup=get_invite_management_keyboard()
    )
    await callback.answer()


# ============================================================================
# SUPPORT TICKETS
# ============================================================================

@admin_router.message(F.text == "💬 Тикеты поддержки")
async def handle_admin_tickets(message: Message, session: AsyncSession):
    """Handle 'Тикеты поддержки' button - show open tickets."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        return

    # Get open tickets
    # TODO: implement get_all_open_tickets in crud
    # For now - stub message
    await message.answer(
        "💬 <b>Тикеты поддержки</b>\n\n"
        "<i>(Функционал в разработке)</i>",
        parse_mode="HTML"
    )


# ============================================================================
# BROADCAST
# ============================================================================

@admin_router.message(F.text == "📊 Рассылка")
async def handle_admin_broadcast(message: Message, state):
    """Handle 'Рассылка' button - start broadcast flow."""
    telegram_id = message.from_user.id

    if telegram_id not in settings.admin_ids:
        return

    await message.answer(
        "📢 <b>Рассылка уведомлений</b>\n\n"
        "Введите текст сообщения для рассылки всем пользователям:\n\n"
        "<i>Поддерживается HTML разметка</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_inline_keyboard()
    )
    # TODO: Create BroadcastStates FSM group
    # await state.set_state(BroadcastStates.enter_message)


# ============================================================================
# CANCEL OPERATION
# ============================================================================

@admin_router.callback_query(F.data == "cancel_operation")
async def callback_cancel_operation(callback: CallbackQuery, state):
    """Handle cancel operation callback."""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Операция отменена")
