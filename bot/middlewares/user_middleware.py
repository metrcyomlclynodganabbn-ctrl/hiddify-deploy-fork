"""
User middleware for Hiddify Bot.
Injects user object into handler dependencies with rate limiting and blocking.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database import crud

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """
    Middleware to inject user object into handlers.

    Features:
    - Gets or creates user from database
    - Checks if user is blocked
    - Updates user activity
    - Rate limiting per user
    """

    def __init__(self):
        super().__init__()
        self._rate_limit = {}  # Simple in-memory rate limit: {user_id: [(timestamp, count)]}

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

        # Rate limiting check
        if not await self._check_rate_limit(telegram_user.id):
            logger.warning(f"Rate limit exceeded for user {telegram_user.id}")
            if isinstance(event, Message):
                await event.answer("⚠️ Слишком много запросов. Попробуйте позже.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Слишком много запросов.", show_alert=True)
            return None

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

        # Update user activity (only if enough time passed)
        # This prevents excessive DB writes
        if await self._should_update_activity(user):
            try:
                await crud.update_user_activity(session, user)
            except Exception as e:
                # Don't fail request if activity update fails
                logger.error(f"Failed to update user activity: {e}")

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

    async def _check_rate_limit(self, user_id: int) -> bool:
        """
        Check rate limit for user.

        Simple in-memory implementation:
        - Max 20 messages per minute
        - Max 100 messages per hour
        """
        import time
        from collections import defaultdict

        now = time.time()

        # Clean old entries
        minute_ago = now - 60
        hour_ago = now - 3600

        # Initialize user tracking if needed
        if user_id not in self._rate_limit:
            self._rate_limit[user_id] = []

        # Filter out old timestamps
        self._rate_limit[user_id] = [
            (ts, count) for ts, count in self._rate_limit[user_id]
            if ts > hour_ago
        ]

        # Count requests in last minute and hour
        last_minute = sum(count for ts, count in self._rate_limit[user_id] if ts > minute_ago)
        last_hour = sum(count for ts, count in self._rate_limit[user_id])

        # Check limits
        if last_minute >= 20 or last_hour >= 100:
            return False

        # Add current request
        self._rate_limit[user_id].append((now, 1))

        return True

    async def _should_update_activity(self, user) -> bool:
        """
        Check if user activity should be updated.

        Only update if last update was more than 5 minutes ago.
        This prevents excessive DB writes.
        """
        if user.updated_at is None:
            return True

        # Check if last update was more than 5 minutes ago
        from datetime import datetime, timezone, timedelta
        if datetime.now(timezone.utc) - user.updated_at > timedelta(minutes=5):
            return True

        return False
