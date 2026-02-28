"""
Database middleware for Hiddify Bot.
Injects database session into handler dependencies.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import get_session_maker

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware to inject database session into handlers.

    Creates async session for each request and injects via data["session"].
    Handles commit/rollback automatically.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Inject database session into handler data."""
        session_maker = get_session_maker()

        async with session_maker() as session:
            # Inject session
            data["session"] = session

            try:
                # Execute handler
                result = await handler(event, data)

                # Commit if handler didn't raise exception
                await session.commit()

                return result

            except Exception as e:
                # Rollback on error
                await session.rollback()
                logger.error(f"Database error, rolled back: {e}")
                raise
