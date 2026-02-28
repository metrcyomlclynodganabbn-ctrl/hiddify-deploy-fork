"""
SQLAlchemy models for Hiddify Bot.
Based on existing SQLite schema with enhancements for v4.0 features.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    BigInteger,
    Numeric,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# ==================== ENUMS ====================

class UserRole(PyEnum):
    """User role."""
    USER = "user"
    MANAGER = "manager"
    ADMIN = "admin"


class SubscriptionStatus(PyEnum):
    """Subscription status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    TRIAL = "trial"
    CANCELLED = "cancelled"


class PaymentProvider(PyEnum):
    """Payment provider."""
    STRIPE = "stripe"  # Deprecated, will be removed
    CRYPTOBOT = "cryptobot"
    TELEGRAM_STARS = "telegram_stars"
    YOOMONEY = "yoomoney"
    PROMO = "promo"  # Promotional code


class PaymentStatus(PyEnum):
    """Payment status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class TicketCategory(PyEnum):
    """Support ticket category."""
    PAYMENT = "payment"
    CONNECTION = "connection"
    SPEED = "speed"
    ACCOUNT = "account"
    OTHER = "other"


class TicketPriority(PyEnum):
    """Support ticket priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(PyEnum):
    """Support ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ReferralStatus(PyEnum):
    """Referral status."""
    PENDING = "pending"  # Referral registered, payment pending
    ACTIVE = "active"    # Referral paid, bonus awarded
    CANCELLED = "cancelled"


# ==================== BASE ====================

class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ==================== USER MODEL ====================

class User(Base):
    """
    User model.

    Based on SQLite users table with all fields preserved.
    """
    __tablename__ = "users"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Telegram data
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_type: Mapped[str] = mapped_column(String(20), default="private", nullable=False)

    # Invite system (v3.x)
    invite_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    invited_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    # Subscription data
    data_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=104857600000, nullable=False)  # 100 GB default
    expire_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Usage tracking
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_connection: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Protocol settings
    vless_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # VPN credentials (VLESS Reality only)
    vless_uuid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Hiddify API integration
    hiddify_uuid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # UUID from Hiddify

    # Trial period (v3.1)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_activated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_data_limit_gb: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Role system (v3.1)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    support_tickets = relationship("SupportTicket", back_populates="user", cascade="all, delete-orphan")
    sent_referrals = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer", cascade="all, delete-orphan")
    received_referral = relationship("Referral", foreign_keys="Referral.referred_id", back_populates="referred", uselist=False)


# ==================== SUBSCRIPTION MODEL ====================

class Subscription(Base):
    """
    Subscription model (v4.0).

    Manages user subscriptions with different plans and statuses.
    """
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Status
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False)  # weekly, monthly, quarterly

    # Data limits
    data_limit_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Dates
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Auto-renewal
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Payment relation
    payment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payments.id"), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment", back_populates="subscription")


# ==================== PAYMENT MODEL ====================

class Payment(Base):
    """
    Payment model (v4.0).

    Supports multiple payment providers: CryptoBot, Telegram Stars, YooMoney.
    Stripe is deprecated and will be removed.
    """
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Payment info
    provider: Mapped[PaymentProvider] = mapped_column(Enum(PaymentProvider), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)  # External payment ID

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)

    # Product details
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)  # weekly, monthly, quarterly
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    data_limit_gb: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata
    invoice_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # For Telegram Stars
    telegram_payment_charge_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # For Telegram Stars
    promo_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # If paid with promo code

    # Referral commission
    referral_id: Mapped[Optional[int]] = mapped_column(ForeignKey("referrals.id"), nullable=True)
    commission_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    commission_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payment", uselist=False)


# ==================== SUPPORT TICKET MODELS ====================

class SupportTicket(Base):
    """
    Support ticket model (v4.0).

    Manages user support tickets with categories and priorities.
    """
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Ticket details
    category: Mapped[TicketCategory] = mapped_column(Enum(TicketCategory), nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority), default=TicketPriority.NORMAL, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False)

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Admin notes
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="support_tickets")
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    """
    Ticket message model (v4.0).

    Stores messages within support tickets.
    """
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Content
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # True if sent by admin

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")


# ==================== REFERRAL MODEL ====================

class Referral(Base):
    """
    Referral model (v4.0).

    Manages referral program with pending/active statuses.
    Replaces old invite system from v3.x.
    """
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Participants
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)  # Who invited
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)  # Who was invited

    # Status and bonus
    status: Mapped[ReferralStatus] = mapped_column(Enum(ReferralStatus), default=ReferralStatus.PENDING, nullable=False)
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # Bonus amount

    # Payment info
    payment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payments.id"), nullable=True)  # Payment that activated referral
    commission_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # When referral became active

    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="sent_referrals")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="received_referral")


# ==================== INVITE MODEL (Legacy v3.x) ====================

class Invite(Base):
    """
    Invite code model (v3.x legacy).

    Preserved for backward compatibility with existing invites.
    New referrals should use Referral model.
    """
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Invite code
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Usage limits
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
