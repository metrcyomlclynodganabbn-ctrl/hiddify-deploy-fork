"""
Admin filters for Hiddify Bot.
Filters to check if user has admin privileges.
"""

import logging
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config.settings import settings

logger = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    """
    Filter to check if user is admin.

    Usage:
        @router.message(IsAdmin())
        @router.callback_query(IsAdmin())
    """

    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        """Check if user is in admin list."""
        user_id = obj.from_user.id

        is_admin = user_id in settings.admin_ids

        if not is_admin:
            logger.debug(f"User {user_id} attempted admin action, denied")

        return is_admin


class IsAdminUser(BaseFilter):
    """
    Filter to check if user object has admin role.

    Usage:
        @router.message(IsAdminUser())
    """

    async def __call__(self, obj: Message | CallbackQuery, user) -> bool:
        """Check if user has admin role."""
        # This filter requires user to be injected via UserMiddleware
        if not user:
            return False

        is_admin = user.role in ["admin", "manager"] or user.is_admin

        if not is_admin:
            logger.debug(
                f"User {user.telegram_id} (role={user.role}) "
                f"attempted admin action, denied"
            )

        return is_admin


# Convenience instances
is_admin = IsAdmin()
is_admin_user = IsAdminUser()
