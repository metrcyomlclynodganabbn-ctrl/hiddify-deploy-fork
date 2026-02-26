"""
Database module for Hiddify VPN Bot

Единый слой работы с БД с:
- Connection pooling для каждого потока
- WAL mode для конкурентного доступа
- Pydantic валидация данных
"""

from .connection import Database, get_db
from .models import InviteCodeCreate, InviteCodeResponse

__all__ = [
    'Database',
    'get_db',
    'InviteCodeCreate',
    'InviteCodeResponse',
]
