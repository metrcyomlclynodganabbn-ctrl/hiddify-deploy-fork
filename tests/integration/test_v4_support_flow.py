"""Интеграционные тесты для v4.0 support tickets flow"""

import pytest
import asyncio
from datetime import datetime

from scripts.database.models import (
    SupportTicketCreate, SupportTicketResponse,
    TicketMessageCreate, TicketMessageResponse,
    TicketCategory, TicketStatus, TicketPriority
)
from scripts.support.ticket_manager import TicketManager


@pytest.mark.asyncio
class TestSupportTicketFlow:
    """Тесты потока тикетов поддержки"""

    async def test_ticket_manager_initialization(self):
        """Тест инициализации менеджера тикетов"""
        manager = TicketManager()

        assert manager is not None

    async def test_ticket_create_validation(self):
        """Тест валидации создания тикета"""
        ticket = SupportTicketCreate(
            user_id=123,
            category=TicketCategory.CONNECTION,
            title="Не подключается",
            description="Проблема с соединением к серверу",
            priority=TicketPriority.NORMAL
        )

        assert ticket.user_id == 123
        assert ticket.category == TicketCategory.CONNECTION
        assert ticket.title == "Не подключается"
        assert ticket.priority == TicketPriority.NORMAL

    async def test_ticket_create_title_too_short_raises(self):
        """Тест слишком короткого заголовка"""
        with pytest.raises(Exception):
            SupportTicketCreate(
                user_id=123,
                category=TicketCategory.CONNECTION,
                title="XY",  # Слишком короткий
                description="Описание"
            )

    async def test_ticket_create_title_too_long_raises(self):
        """Тест слишком длинного заголовка"""
        with pytest.raises(Exception):
            SupportTicketCreate(
                user_id=123,
                category=TicketCategory.CONNECTION,
                title="X" * 201,  # Слишком длинный
                description="Описание"
            )

    async def test_ticket_create_description_too_short_raises(self):
        """Тест слишком короткого описания"""
        with pytest.raises(Exception):
            SupportTicketCreate(
                user_id=123,
                category=TicketCategory.CONNECTION,
                title="Заголовок",
                description="XY"  # Слишком короткое
            )

    async def test_ticket_message_create_validation(self):
        """Тест валидации создания сообщения тикета"""
        message = TicketMessageCreate(
            ticket_id=1,
            user_id=123,
            message="Здравствуйте, у меня проблема",
            is_admin=False
        )

        assert message.ticket_id == 1
        assert message.user_id == 123
        assert message.is_admin is False

    async def test_ticket_category_enum(self):
        """Тест enum категорий тикетов"""
        assert TicketCategory.PAYMENT == "payment"
        assert TicketCategory.CONNECTION == "connection"
        assert TicketCategory.SPEED == "speed"
        assert TicketCategory.ACCOUNT == "account"
        assert TicketCategory.OTHER == "other"

    async def test_ticket_status_enum(self):
        """Тест enum статусов тикетов"""
        assert TicketStatus.OPEN == "open"
        assert TicketStatus.IN_PROGRESS == "in_progress"
        assert TicketStatus.WAITING == "waiting"
        assert TicketStatus.RESOLVED == "resolved"
        assert TicketStatus.CLOSED == "closed"

    async def test_ticket_priority_enum(self):
        """Тест enum приоритетов тикетов"""
        assert TicketPriority.LOW == "low"
        assert TicketPriority.NORMAL == "normal"
        assert TicketPriority.HIGH == "high"
        assert TicketPriority.URGENT == "urgent"


@pytest.mark.asyncio
class TestSupportTicketIntegration:
    """Интеграционные тесты системы поддержки"""

    async def test_full_ticket_flow_simulation(self):
        """Симуляция полного потока тикета"""
        # 1. Создание тикета
        ticket = SupportTicketCreate(
            user_id=123,
            category=TicketCategory.CONNECTION,
            title="Не подключается",
            description="Проблема с соединением к серверу",
            priority=TicketPriority.NORMAL
        )

        assert ticket.user_id == 123

        # 2. В реальной системе здесь было бы создание в БД
        # result = await ticket_manager.create_ticket(ticket)

        # 3. Добавление сообщения пользователем
        message = TicketMessageCreate(
            ticket_id=1,
            user_id=123,
            message="Здравствуйте, у меня проблема",
            is_admin=False
        )

        # 4. В реальной системе здесь было бы добавление сообщения
        # msg_result = await ticket_manager.add_message(message)

        # 5. Ответ админа
        admin_message = TicketMessageCreate(
            ticket_id=1,
            user_id=1,  # Admin ID
            message="Здравствуйте! Мы решаем проблему.",
            is_admin=True
        )

        # 6. Изменение статуса
        # await ticket_manager.update_ticket_status(1, TicketStatus.IN_PROGRESS)

        # 7. Получение сообщений тикета
        # messages = await ticket_manager.get_ticket_messages(1)
        # assert len(messages) >= 2
