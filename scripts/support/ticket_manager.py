"""
Менеджер тикетов поддержки

Модуль обеспечивает создание и управление тикетами техподдержки.
Пользователи могут создавать тикеты, админы - отвечать на них.
"""

import os
import logging
from typing import Optional, Dict, List
from datetime import datetime

from ..database.connection import get_db_connection
from ..database.models import (
    SupportTicketCreate, SupportTicketResponse,
    TicketMessageCreate, TicketMessageResponse,
    TicketCategory, TicketStatus, TicketPriority
)

logger = logging.getLogger(__name__)


class TicketError(Exception):
    """Исключение для ошибок тикетов"""
    pass


class TicketManager:
    """
    Менеджер для работы с тикетами поддержки

    Тикеты хранятся в таблицах:
    - support_tickets: Основная информация
    - ticket_messages: Сообщения в тикете
    """

    async def create_ticket(
        self,
        ticket: SupportTicketCreate
    ) -> SupportTicketResponse:
        """Создать новый тикет

        Args:
            ticket: Данные для создания тикета

        Returns:
            SupportTicketResponse с данными созданного тикета

        Raises:
            TicketError: Ошибка создания тикета
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                now = datetime.now()

                # Создание тикета
                cursor = await conn.execute(
                    """INSERT INTO support_tickets
                    (user_id, status, category, priority, title, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ticket.user_id,
                        TicketStatus.OPEN,
                        ticket.category,
                        ticket.priority,
                        ticket.title,
                        ticket.description,
                        now,
                        now
                    )
                )
                ticket_id = cursor.lastrowid
                await conn.commit()

                # Получение созданного тикета
                row = await conn.execute(
                    "SELECT * FROM support_tickets WHERE id = ?",
                    (ticket_id,)
                )
                result = row.fetchone()

                logger.info(f"Тикет #{ticket_id} создан пользователем {ticket.user_id}")

                return SupportTicketResponse(
                    id=result[0],
                    user_id=result[1],
                    status=result[2],
                    category=result[3],
                    priority=result[4],
                    title=result[5],
                    description=result[6],
                    created_at=result[7],
                    updated_at=result[8],
                    resolved_at=result[9],
                    admin_notes=result[10]
                )

        except Exception as e:
            logger.error(f"Ошибка создания тикета: {e}")
            raise TicketError(f"Ошибка создания тикета: {e}")

    async def get_ticket(
        self,
        ticket_id: int
    ) -> Optional[SupportTicketResponse]:
        """Получить тикет по ID

        Args:
            ticket_id: ID тикета

        Returns:
            SupportTicketResponse или None
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                row = await conn.execute(
                    "SELECT * FROM support_tickets WHERE id = ?",
                    (ticket_id,)
                )
                result = row.fetchone()

                if not result:
                    return None

                return SupportTicketResponse(
                    id=result[0],
                    user_id=result[1],
                    status=result[2],
                    category=result[3],
                    priority=result[4],
                    title=result[5],
                    description=result[6],
                    created_at=result[7],
                    updated_at=result[8],
                    resolved_at=result[9],
                    admin_notes=result[10]
                )

        except Exception as e:
            logger.error(f"Ошибка получения тикета: {e}")
            return None

    async def list_tickets(
        self,
        user_id: int = None,
        status: TicketStatus = None,
        category: TicketCategory = None,
        limit: int = 50
    ) -> List[SupportTicketResponse]:
        """Получить список тикетов

        Args:
            user_id: Фильтр по пользователю
            status: Фильтр по статусу
            category: Фильтр по категории
            limit: Лимит записей

        Returns:
            Список тикетов
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                query = "SELECT * FROM support_tickets WHERE 1=1"
                params = []

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                rows = await conn.execute(query, params)
                results = []

                for row in rows.fetchall():
                    results.append(SupportTicketResponse(
                        id=row[0],
                        user_id=row[1],
                        status=row[2],
                        category=row[3],
                        priority=row[4],
                        title=row[5],
                        description=row[6],
                        created_at=row[7],
                        updated_at=row[8],
                        resolved_at=row[9],
                        admin_notes=row[10]
                    ))

                return results

        except Exception as e:
            logger.error(f"Ошибка получения списка тикетов: {e}")
            return []

    async def update_ticket_status(
        self,
        ticket_id: int,
        status: TicketStatus,
        admin_id: int = None
    ) -> bool:
        """Обновить статус тикета

        Args:
            ticket_id: ID тикета
            status: Новый статус
            admin_id: ID админа (опционально)

        Returns:
            True если успешно
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                now = datetime.now()

                update_fields = {
                    'status': status,
                    'updated_at': now
                }

                # Установка resolved_at при закрытии
                if status == TicketStatus.RESOLVED or status == TicketStatus.CLOSED:
                    update_fields['resolved_at'] = now

                # Формирование SQL
                set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
                params = list(update_fields.values()) + [ticket_id]

                await conn.execute(
                    f"UPDATE support_tickets SET {set_clause} WHERE id = ?",
                    params
                )
                await conn.commit()

                logger.info(f"Тикет #{ticket_id} статус изменён на {status} админом {admin_id}")

                return True

        except Exception as e:
            logger.error(f"Ошибка обновления статуса тикета: {e}")
            return False

    async def add_message(
        self,
        message: TicketMessageCreate
    ) -> TicketMessageResponse:
        """Добавить сообщение в тикет

        Args:
            message: Данные сообщения

        Returns:
            TicketMessageResponse с данными созданного сообщения
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                now = datetime.now()

                # Создание сообщения
                cursor = await conn.execute(
                    """INSERT INTO ticket_messages
                    (ticket_id, user_id, message, is_admin, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (message.ticket_id, message.user_id, message.message, message.is_admin, now)
                )
                message_id = cursor.lastrowid

                # Обновление updated_at в тикете
                await conn.execute(
                    "UPDATE support_tickets SET updated_at = ? WHERE id = ?",
                    (now, message.ticket_id)
                )
                await conn.commit()

                logger.info(f"Сообщение #{message_id} добавлено в тикет #{message.ticket_id}")

                return TicketMessageResponse(
                    id=message_id,
                    ticket_id=message.ticket_id,
                    user_id=message.user_id,
                    message=message.message,
                    is_admin=message.is_admin,
                    created_at=now
                )

        except Exception as e:
            logger.error(f"Ошибка добавления сообщения: {e}")
            raise TicketError(f"Ошибка добавления сообщения: {e}")

    async def get_ticket_messages(
        self,
        ticket_id: int
    ) -> List[TicketMessageResponse]:
        """Получить сообщения тикета

        Args:
            ticket_id: ID тикета

        Returns:
            Список сообщений
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                rows = await conn.execute(
                    """SELECT * FROM ticket_messages
                    WHERE ticket_id = ?
                    ORDER BY created_at ASC""",
                    (ticket_id,)
                )
                results = []

                for row in rows.fetchall():
                    results.append(TicketMessageResponse(
                        id=row[0],
                        ticket_id=row[1],
                        user_id=row[2],
                        message=row[3],
                        is_admin=row[4],
                        created_at=row[5]
                    ))

                return results

        except Exception as e:
            logger.error(f"Ошибка получения сообщений тикета: {e}")
            return []

    async def get_user_open_tickets_count(
        self,
        user_id: int
    ) -> int:
        """Получить количество открытых тикетов пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Количество открытых тикетов
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                row = await conn.execute(
                    """SELECT COUNT(*) FROM support_tickets
                    WHERE user_id = ? AND status IN (?, ?)""",
                    (user_id, TicketStatus.OPEN, TicketStatus.IN_PROGRESS)
                )
                result = row.fetchone()
                return result[0] if result else 0

        except Exception as e:
            logger.error(f"Ошибка подсчёта открытых тикетов: {e}")
            return 0


# Глобальный экземпляр менеджера
ticket_manager = TicketManager()
