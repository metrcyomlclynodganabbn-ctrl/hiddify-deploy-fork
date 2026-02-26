"""
Pydantic models для валидации данных

Использует Pydantic для строгой типизации и валидации:
- InviteCodeCreate - для создания инвайт-кодов
- InviteCodeResponse - для ответов API
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class InviteCodeCreate(BaseModel):
    """
    Модель для создания инвайт-кода с валидацией

    Attributes:
        code: Код инвайта (формат INV_xxxxx, 8-50 символов)
        created_by: Telegram ID создателя
        max_uses: Максимальное количество использований (1-1000)
        expires_at: Опциональный срок действия
    """

    code: str = Field(
        ...,
        min_length=8,
        max_length=50,
        pattern=r'^INV_[a-f0-9]+$',
        description="Код инвайта должен начинаться с INV_ и содержать hex-символы"
    )
    created_by: int = Field(
        ...,
        gt=0,
        description="Telegram ID создателя (должен быть положительным)"
    )
    max_uses: int = Field(
        default=1,
        gt=0,
        le=1000,
        description="Максимальное количество использований (1-1000)"
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Опциональный срок действия кода"
    )

    @field_validator('expires_at')
    @classmethod
    def validate_expiration_not_in_past(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Проверить что срок действия не в прошлом"""
        if v and v < datetime.now():
            raise ValueError('Срок действия не может быть в прошлом')
        return v


class InviteCodeResponse(BaseModel):
    """
    Модель ответа с данными инвайт-кода

    Attributes:
        id: ID записи в БД
        code: Код инвайта
        created_by: Telegram ID создателя
        created_at: Время создания
        expires_at: Срок действия (если есть)
        max_uses: Максимальное количество использований
        used_count: Текущее количество использований
        is_active: Активен ли код
    """

    id: int
    code: str
    created_by: int
    created_at: datetime
    expires_at: Optional[datetime]
    max_uses: int
    used_count: int
    is_active: bool


class InviteCodeUseResult(BaseModel):
    """
    Модель результата использования инвайт-кода

    Attributes:
        success: Успешно ли использован код
        message: Сообщение о результате
        invite_data: Данные инвайта (если успешно)
    """

    success: bool
    message: str
    invite_data: Optional[InviteCodeResponse] = None


class ValidationError(BaseModel):
    """
    Модель ошибки валидации

    Attributes:
        field: Поле с ошибкой
        message: Сообщение об ошибке
    """

    field: str
    message: str
