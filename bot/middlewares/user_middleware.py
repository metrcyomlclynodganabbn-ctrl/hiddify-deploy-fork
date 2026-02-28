"""
User middleware for Hiddify Bot.
Injects user object into handler dependencies.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """
    Middleware to inject user object into handlers.

    Gets or creates user from database and injects via data["user"].
    Blocks access if user.is_blocked == True.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Inject user object into handler data."""
        session: AsyncSession = data.get("session")

        # Get Telegram user from event
        telegram_user = self._extract_telegram_user(event)
        if not telegram_user:
            # No user in this event, proceed
            return await handler(event, data)

        # Get or create user
        user = await crud.get_or_create_user(
            session=session,
            telegram_id=telegram_user.id,
            telegram_username=telegram_user.username,
            telegram_first_name=telegram_user.first_name,
        )

        # Check if user is blocked
        if user.is_blocked:
            logger.warning(
                f"Blocked user attempted access: telegram_id={user.telegram_id}, "
                f"username={user.telegram_username}, user_id={user.id}"
            )

            # Send notification to user if possible
            if isinstance(event, Message):
                await event.answer(
                    "🚫 Ваш аккаунт заблокирован.\n\n"
                    "Обратитесь в поддержку для уточнения причин."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "🚫 Ваш аккаунт заблокирован",
                    show_alert=True
                )

            # Stop handler execution
            return None

        # Inject user
        data["user"] = user

        return await handler(event, data)

    def _extract_telegram_user(self, event: TelegramObject):
        """Extract Telegram user from various event types."""
        if isinstance(event, Message):
            return event.from_user
        elif isinstance(event, CallbackQuery):
            return event.from_user
        elif isinstance(event, Update):
            if event.message:
                return event.message.from_user
            elif event.callback_query:
                return event.callback_query.from_user
        return None
