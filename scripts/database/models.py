"""
Pydantic models для валидации данных

Использует Pydantic для строгой типизации и валидации:
- InviteCodeCreate - для создания инвайт-кодов
- InviteCodeResponse - для ответов API
- Payment* - модели для платежной системы
- SupportTicket* - модели для тикетов поддержки
- Referral* - модели для реферальной системы
- Subscription* - модели для подписок
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum


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


# ============================================================================
# PAYMENT MODELS (v4.0)
# ============================================================================

class PaymentMethod(str, Enum):
    """Методы оплаты"""
    CARD = "card"
    CRYPTO = "crypto"
    PROMO = "promo"


class PaymentStatus(str, Enum):
    """Статусы платежа"""
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class PaymentProvider(str, Enum):
    """Платежные провайдеры"""
    STRIPE = "stripe"
    TON = "ton"
    BTC = "btc"
    MANUAL = "manual"


class PaymentCreate(BaseModel):
    """
    Модель для создания платежа

    Attributes:
        user_id: ID пользователя
        amount: Сумма платежа
        currency: Код валюты (USD, EUR, RUB)
        method: Метод оплаты
        plan_code: Код плана подписки
    """

    user_id: int = Field(..., gt=0, description="ID пользователя")
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Сумма платежа")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Код валюты")
    method: PaymentMethod = Field(..., description="Метод оплаты")
    plan_code: Optional[str] = Field(None, max_length=50, description="Код плана подписки")


class PaymentResponse(BaseModel):
    """
    Модель ответа с данными платежа

    Attributes:
        id: ID платежа в БД
        provider_id: ID платежа у провайдера
        user_id: ID пользователя
        amount: Сумма платежа
        currency: Код валюты
        status: Статус платежа
        provider: Платежный провайдер
        checkout_url: URL для оплаты
        created_at: Дата создания
        paid_at: Дата оплаты
    """

    id: int
    provider_id: Optional[str] = None
    user_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    provider: PaymentProvider
    checkout_url: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None


class PaymentWebhook(BaseModel):
    """
    Модель для webhook от платежной системы

    Attributes:
        provider: Платежный провайдер
        provider_id: ID платежа у провайдера
        status: Новый статус
        raw_data: Сырые данные webhook
    """

    provider: PaymentProvider
    provider_id: str
    status: PaymentStatus
    raw_data: Optional[dict] = None


# ============================================================================
# SUPPORT TICKET MODELS (v4.0)
# ============================================================================

class TicketCategory(str, Enum):
    """Категории тикетов"""
    PAYMENT = "payment"
    CONNECTION = "connection"
    SPEED = "speed"
    ACCOUNT = "account"
    OTHER = "other"


class TicketStatus(str, Enum):
    """Статусы тикетов"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Приоритеты тикетов"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SupportTicketCreate(BaseModel):
    """
    Модель для создания тикета поддержки

    Attributes:
        user_id: ID пользователя
        category: Категория проблемы
        title: Заголовок (краткое описание)
        description: Подробное описание
        priority: Приоритет (опционально)
    """

    user_id: int = Field(..., gt=0, description="ID пользователя")
    category: TicketCategory = Field(..., description="Категория проблемы")
    title: str = Field(..., min_length=1, max_length=200, description="Заголовок")
    description: str = Field(..., min_length=1, max_length=5000, description="Описание")
    priority: TicketPriority = Field(default=TicketPriority.NORMAL, description="Приоритет")


class SupportTicketResponse(BaseModel):
    """
    Модель ответа с данными тикета

    Attributes:
        id: ID тикета
        user_id: ID пользователя
        status: Статус
        category: Категория
        priority: Приоритет
        title: Заголовок
        description: Описание
        created_at: Дата создания
        updated_at: Дата обновления
        resolved_at: Дата решения
        admin_notes: Заметки админа
    """

    id: int
    user_id: int
    status: TicketStatus
    category: TicketCategory
    priority: TicketPriority
    title: str
    description: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    admin_notes: Optional[str] = None


class TicketMessageCreate(BaseModel):
    """
    Модель для добавления сообщения в тикет

    Attributes:
        ticket_id: ID тикета
        user_id: ID пользователя (отправитель)
        message: Текст сообщения
        is_admin: Сообщение от админа
    """

    ticket_id: int = Field(..., gt=0, description="ID тикета")
    user_id: int = Field(..., gt=0, description="ID пользователя")
    message: str = Field(..., min_length=1, max_length=2000, description="Сообщение")
    is_admin: bool = Field(default=False, description="Сообщение от админа")


class TicketMessageResponse(BaseModel):
    """
    Модель ответа с сообщением тикета

    Attributes:
        id: ID сообщения
        ticket_id: ID тикета
        user_id: ID отправителя
        message: Текст сообщения
        is_admin: От админа ли
        created_at: Дата создания
    """

    id: int
    ticket_id: int
    user_id: int
    message: str
    is_admin: bool
    created_at: datetime


# ============================================================================
# REFERRAL MODELS (v4.0)
# ============================================================================

class ReferralCreate(BaseModel):
    """
    Модель для создания реферальной записи

    Attributes:
        referrer_id: ID пригласившего
        referred_id: ID приглашённого
        bonus_amount: Сумма бонуса
    """

    referrer_id: int = Field(..., gt=0, description="ID пригласившего")
    referred_id: int = Field(..., gt=0, description="ID приглашённого")
    bonus_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2, description="Сумма бонуса")


class ReferralResponse(BaseModel):
    """
    Модель ответа с данными реферала

    Attributes:
        id: ID записи
        referrer_id: ID пригласившего
        referred_id: ID приглашённого
        created_at: Дата создания
        bonus_amount: Заработанная сумма
        status: Статус (active, pending, paid)
    """

    id: int
    referrer_id: int
    referred_id: int
    created_at: datetime
    bonus_amount: Decimal
    status: str


class ReferralStats(BaseModel):
    """
    Модель статистики рефералов

    Attributes:
        total_referrals: Общее количество рефералов
        active_referrals: Активные рефералы
        total_earned: Общий заработок
        pending_payout: Ожидает выплаты
    """

    total_referrals: int
    active_referrals: int
    total_earned: Decimal
    pending_payout: Decimal


# ============================================================================
# SUBSCRIPTION MODELS (v4.0)
# ============================================================================

class SubscriptionPlan(str, Enum):
    """Планы подписок"""
    TRIAL = "trial"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"


class SubscriptionStatus(str, Enum):
    """Статусы подписки"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class SubscriptionCreate(BaseModel):
    """
    Модель для создания подписки

    Attributes:
        user_id: ID пользователя
        plan_code: Код плана
        auto_renew: Автоматическое продление
    """

    user_id: int = Field(..., gt=0, description="ID пользователя")
    plan_code: SubscriptionPlan = Field(..., description="Код плана")
    auto_renew: bool = Field(default=False, description="Автопродление")


class SubscriptionResponse(BaseModel):
    """
    Модель ответа с данными подписки

    Attributes:
        id: ID подписки
        user_id: ID пользователя
        plan_code: Код плана
        status: Статус подписки
        started_at: Дата начала
        expires_at: Дата окончания
        auto_renew: Автопродление
        data_limit_bytes: Лимит трафика
        used_bytes: Использовано трафика
    """

    id: int
    user_id: int
    plan_code: SubscriptionPlan
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime
    auto_renew: bool
    data_limit_bytes: Optional[int] = None
    used_bytes: int = 0


class SubscriptionPlanDetails(BaseModel):
    """
    Модель деталей плана подписки

    Attributes:
        code: Код плана
        name: Название
        description: Описание
        price: Цена
        currency: Код валюты
        duration_days: Длительность в днях
        data_limit_bytes: Лимит трафика
        features: Список функций
    """

    code: SubscriptionPlan
    name: str
    description: str
    price: Decimal
    currency: str
    duration_days: int
    data_limit_bytes: Optional[int] = None
    features: List[str] = []


# ============================================================================
# VPN ACCOUNT MODELS (v4.0)
# ============================================================================

class VPNProtocol(str, Enum):
    """VPN протоколы"""
    VLESS_REALITY = "vless_reality"
    HYSTERIA2 = "hysteria2"
    SHADOWSOCKS = "shadowsocks"
    TROJAN = "trojan"


class VPNAccountCreate(BaseModel):
    """
    Модель для создания VPN аккаунта

    Attributes:
        user_id: ID пользователя
        server_group: Группа серверов
        protocol: Протокол
    """

    user_id: int = Field(..., gt=0, description="ID пользователя")
    server_group: str = Field(..., max_length=50, description="Группа серверов")
    protocol: VPNProtocol = Field(..., description="Протокол")


class VPNAccountResponse(BaseModel):
    """
    Модель ответа с данными VPN аккаунта

    Attributes:
        id: ID аккаунта
        external_id: Внешний ID (в Hiddify)
        user_id: ID пользователя
        server_group: Группа серверов
        protocol: Протокол
        status: Статус
        created_at: Дата создания
        config: Конфигурация (JSON)
    """

    id: int
    external_id: str
    user_id: int
    server_group: str
    protocol: VPNProtocol
    status: str
    created_at: datetime
    config: Optional[dict] = None


# ============================================================================
# TRAFFIC USAGE MODELS (v4.0)
# ============================================================================

class TrafficUsageCreate(BaseModel):
    """
    Модель для записи использования трафика

    Attributes:
        vpn_account_id: ID VPN аккаунта
        period_start: Начало периода
        period_end: Конец периода
        bytes_up: Отправлено байт
        bytes_down: Получено байт
    """

    vpn_account_id: int = Field(..., gt=0, description="ID VPN аккаунта")
    period_start: datetime = Field(..., description="Начало периода")
    period_end: datetime = Field(..., description="Конец периода")
    bytes_up: int = Field(default=0, ge=0, description="Отправлено байт")
    bytes_down: int = Field(default=0, ge=0, description="Получено байт")


class TrafficUsageResponse(BaseModel):
    """
    Модель ответа с данными о трафике

    Attributes:
        id: ID записи
        vpn_account_id: ID VPN аккаунта
        period_start: Начало периода
        period_end: Конец периода
        bytes_up: Отправлено байт
        bytes_down: Получено байт
        bytes_total: Всего байт
    """

    id: int
    vpn_account_id: int
    period_start: datetime
    period_end: datetime
    bytes_up: int
    bytes_down: int
    bytes_total: int
