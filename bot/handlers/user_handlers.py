"""
User handlers for Hiddify Bot.
Contains all user-facing command and callback handlers.
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Create router for user handlers
user_router = Router()


@user_router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command."""
    await message.answer(
        "👋 Добро пожаловать в Hiddify Bot!\n\n"
        "🔧 Бот находится в разработке.\n"
        "Скоро здесь появится полноценное VPN управление."
    )
    logger.info(f"User {message.from_user.id} called /start")


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
        "🔧 Бот в разработке..."
    )


@user_router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Handle /cancel command."""
    await message.answer("❌ Операция отменена")


@user_router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Handle /profile command."""
    await message.answer("👤 Профиль пользователя")
