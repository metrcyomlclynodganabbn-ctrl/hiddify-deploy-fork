"""
Database connection layer with WAL mode and connection pooling

Модуль обеспечивает безопасный конкурентный доступ к SQLite через:
- Thread-local connections (каждый поток имеет своё соединение)
- WAL mode (Write-Ahead Logging) для параллельного чтения/записи
- Context manager для транзакций
"""

import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

# Путь к БД относительно этого файла
DB_PATH = Path(__file__).parent.parent.parent / "data" / "bot.db"


class Database:
    """
    SQLite connection pool с WAL mode для конкурентного доступа

    Использует паттерн Singleton с thread-local storage:
    - Каждый поток получает своё соединение
    - WAL mode позволяет параллельные чтения при записи
    - Автоматическое управление транзакциями
    """

    _instance: Optional['Database'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'Database':
        """Singleton с double-checked locking"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Инициализация (происходит один раз для singleton)"""
        if self._initialized:
            return

        # Thread-local storage для connections
        self._local = threading.local()
        self._init_db_path()
        self._initialized = True

    def _init_db_path(self) -> None:
        """Создать директорию для БД если не существует"""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """
        Получить connection для текущего потока с WAL mode

        Connection создаётся один раз на поток и переиспользуется.
        WAL mode включается автоматически.

        Returns:
            sqlite3.Connection: Соединение с настроенным WAL mode
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row

            # Включить WAL mode для конкурентного доступа
            self._local.conn.execute('PRAGMA journal_mode=WAL')
            self._local.conn.execute('PRAGMA busy_timeout=30000')
            self._local.conn.execute('PRAGMA foreign_keys=ON')

        return self._local.conn

    @contextmanager
    def transaction(self):
        """
        Context manager для транзакций с автоматическим commit/rollback

        Usage:
            with db.transaction():
                # выполнить операции
                cursor.execute('INSERT INTO ...')

        Yields:
            sqlite3.Connection: Соединение в рамках транзакции
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        """Закрыть connection для текущего потока"""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None


# Singleton instance
_db: Optional[Database] = None


def get_db() -> Database:
    """
    Получить singleton instance Database

    Returns:
        Database: Единственный instance Database для приложения
    """
    global _db
    if _db is None:
        _db = Database()
    return _db
