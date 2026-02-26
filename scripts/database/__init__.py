"""Database модуль для работы с БД"""

from .connection import Database
from .models import *

# Создаём глобальный экземпляр
db = Database()

__all__ = [
    'Database',
    'db',
]
