"""
Hiddify Bot - Main entry point.
Aiogram 3 async Telegram bot for VPN management.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault
import logging

logger = logging.getLogger(__name__)

from config.settings import settings
from config.logging_config import setup_logging
from database.base import init_db, close_db
from services.hiddify_client import get_hiddify_client, close_hiddify_client
from bot.webhook_server import start_webhook_server

# Setup logging
setup_logging()

# Import routers
from bot.handlers.user_handlers import user_router
from bot.handlers.admin_handlers import admin_router
from bot.handlers.payment_handlers import payment_router

# Import middlewares (currently empty stubs)
from bot.middlewares.db_middleware import DatabaseMiddleware
from bot.middlewares.user_middleware import UserMiddleware


# ==================== BOT COMMANDS ====================

async def set_bot_commands(bot: Bot):
    """Set bot commands menu."""
    commands = [
        BotCommand(command="start", description="Главное меню / Начать"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить текущую операцию"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="admin", description="Панель администратора"),
    ]

    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot commands set")


# ==================== SHUTDOWN ====================

async def shutdown(dispatcher: Dispatcher, bot: Bot, webhook_runner=None):
    """Graceful shutdown."""
    logger.info("Shutting down...")

    # Stop webhook server
    if webhook_runner:
        try:
            await webhook_runner.cleanup()
            logger.info("Webhook server stopped")
        except Exception as e:
            logger.error(f"Error stopping webhook server: {e}")

    # Stop dispatcher
    await dispatcher.fsm.storage.close()

    # Close Hiddify API client
    await close_hiddify_client()

    # Close database
    await close_db()

    # Close bot session
    await bot.session.close()

    logger.info("Bot stopped")


# ==================== MAIN ====================

async def main():
    """Main function to run the bot."""
    logger.info("Starting Hiddify Bot (Aiogram 3)...")

    # Initialize database
    logger.info("Initializing database...")
    await init_db()

    # Initialize Hiddify API client
    logger.info("Initializing Hiddify API client...")
    hiddify_client = get_hiddify_client()
    if await hiddify_client.test_connection():
        logger.info("Hiddify API connection successful")
    else:
        logger.warning("Hiddify API connection failed, will retry later")

    # Create bot instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Create dispatcher
    dp = Dispatcher()

    # Register middleware (order matters!)
    # Database session injection -> User object injection
    dp.update.outer_middleware(DatabaseMiddleware())
    dp.update.outer_middleware(UserMiddleware())

    # Register routers
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(payment_router)

    # Set bot commands
    await set_bot_commands(bot)

    # Start webhook server (parallel to bot polling)
    webhook_runner = None
    if settings.cryptobot_api_token:
        try:
            logger.info("Starting webhook server...")
            webhook_runner = await start_webhook_server(port=8081)
            logger.info("Webhook server started on port 8081")
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(shutdown(dp, bot, webhook_runner))
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start polling
    logger.info("Bot started successfully!")
    logger.info(f"Bot configured for: {settings.panel_domain}")
    logger.info(f"Admins: {settings.admin_ids}")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
                "pre_checkout_query",
                "chat_join_request",
            ],
        )
    except Exception as e:
        logger.error(f"Error during polling: {e}")
    finally:
        await shutdown(dp, bot, webhook_runner)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
