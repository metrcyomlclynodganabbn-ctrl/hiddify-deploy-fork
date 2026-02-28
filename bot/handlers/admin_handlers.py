"""
Admin handlers for Hiddify Bot.
Contains all admin-only command and callback handlers.
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import settings

logger = logging.getLogger(__name__)

# Create router for admin handlers
admin_router = Router()


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    # Check if user is admin
    if message.from_user.id not in settings.admin_ids:
        await message.answer("🚫 У вас нет прав администратора")
        return

    await message.answer(
        "🔧 <b>Панель администратора</b>\n\n"
        "🔧 Бот находится в разработке.\n"
        "Скоро здесь появится админ-панель."
    )
    logger.info(f"Admin {message.from_user.id} accessed admin panel")
