"""
CRUD operations for Hiddify Bot database models.
All functions are async and use SQLAlchemy 2.0.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    User,
    Subscription,
    SubscriptionStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    SupportTicket,
    TicketStatus,
    TicketMessage,
    Referral,
    ReferralStatus,
    Invite,
)

logger = logging.getLogger(__name__)


# ============================================================================
# USER CRUD
# ============================================================================

async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """Get user by Telegram ID."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(
    session: AsyncSession,
    user_id: int
) -> Optional[User]:
    """Get user by primary key ID."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_invite_code(
    session: AsyncSession,
    invite_code: str
) -> Optional[User]:
    """Get user by invite code."""
    result = await session.execute(
        select(User).where(User.invite_code == invite_code)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    telegram_username: Optional[str] = None,
    telegram_first_name: Optional[str] = None,
    invited_by: Optional[int] = None,
    data_limit_bytes: int = 104857600000,  # 100 GB
    expire_days: int = 30,
    role: str = "user",
) -> User:
    """Create new user."""
    import uuid
    import os

    # Generate VPN credentials (VLESS Reality only)
    vless_uuid = str(uuid.uuid4())

    # Generate invite code
    invite_code = f"INV_{os.urandom(8).hex()}"

    # Calculate expiry
    expires_at = datetime.now() + timedelta(days=expire_days) if expire_days else None

    user = User(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        telegram_first_name=telegram_first_name,
        invited_by=invited_by,
        invite_code=invite_code,
        data_limit_bytes=data_limit_bytes,
        expire_days=expire_days,
        expires_at=expires_at,
        vless_uuid=vless_uuid,
        role=role,
    )

    session.add(user)
    await session.flush()  # Flush to get ID without committing
    logger.info(f"User created: telegram_id={telegram_id}, username={telegram_username}")
    return user


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    telegram_username: Optional[str] = None,
    telegram_first_name: Optional[str] = None,
    telegram_last_name: Optional[str] = None,
) -> User:
    """Get existing user or create new one."""
    user = await get_user_by_telegram_id(session, telegram_id)

    if not user:
        user = await create_user(
            session=session,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
        )
        await session.commit()
        await session.refresh(user)

    return user


async def update_user(
    session: AsyncSession,
    user: User,
) -> User:
    """Update user."""
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_activity(
    session: AsyncSession,
    user: User,
) -> User:
    """Update user last_activity timestamp."""
    user.updated_at = datetime.now()
    await session.commit()
    return user


async def block_user(
    session: AsyncSession,
    user_id: int,
    block: bool = True,
) -> Optional[User]:
    """Block or unblock user."""
    user = await get_user_by_id(session, user_id)
    if user:
        user.is_blocked = block
        await session.commit()
        await session.refresh(user)
    return user


async def get_users_list(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = False,
) -> List[User]:
    """Get list of users with pagination."""
    query = select(User).order_by(User.created_at.desc())

    if active_only:
        query = query.where(User.is_active == True)

    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_users_stats(
    session: AsyncSession,
) -> dict:
    """Get users statistics."""
    total = await session.execute(select(func.count(User.id)))
    total_users = total.scalar()

    active = await session.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active.scalar()

    trial = await session.execute(
        select(func.count(User.id)).where(User.is_trial == True)
    )
    trial_users = trial.scalar()

    blocked = await session.execute(
        select(func.count(User.id)).where(User.is_blocked == True)
    )
    blocked_users = blocked.scalar()

    return {
        "total_users": total_users or 0,
        "active_users": active_users or 0,
        "trial_users": trial_users or 0,
        "blocked_users": blocked_users or 0,
    }


# ============================================================================
# SUBSCRIPTION CRUD
# ============================================================================

async def get_active_subscription(
    session: AsyncSession,
    user_id: int,
) -> Optional[Subscription]:
    """Get user's active subscription."""
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(
            or_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.status == SubscriptionStatus.TRIAL,
            )
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_subscription(
    session: AsyncSession,
    user_id: int,
    plan_name: str,
    duration_days: int,
    data_limit_gb: int,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    auto_renew: bool = False,
) -> Subscription:
    """Create new subscription."""
    expires_at = datetime.now() + timedelta(days=duration_days)

    subscription = Subscription(
        user_id=user_id,
        plan_name=plan_name,
        status=status,
        data_limit_bytes=data_limit_gb * 1024**3,
        expires_at=expires_at,
        duration_days=duration_days,
        auto_renew=auto_renew,
    )

    session.add(subscription)
    await session.flush()
    return subscription


# ============================================================================
# PAYMENT CRUD
# ============================================================================

async def get_payment_by_provider_id(
    session: AsyncSession,
    provider_payment_id: str,
) -> Optional[Payment]:
    """Get payment by provider's payment ID."""
    result = await session.execute(
        select(Payment).where(Payment.provider_payment_id == provider_payment_id)
    )
    return result.scalar_one_or_none()


async def create_payment(
    session: AsyncSession,
    user_id: int,
    provider: PaymentProvider,
    provider_payment_id: str,
    amount: Decimal,
    currency: str,
    plan_code: str,
    duration_days: int,
    data_limit_gb: int,
    promo_code: Optional[str] = None,
) -> Payment:
    """Create new payment."""
    payment = Payment(
        user_id=user_id,
        provider=provider,
        provider_payment_id=provider_payment_id,
        amount=amount,
        currency=currency,
        plan_code=plan_code,
        duration_days=duration_days,
        data_limit_gb=data_limit_gb,
        promo_code=promo_code,
    )

    session.add(payment)
    await session.flush()
    return payment


async def update_payment_status(
    session: AsyncSession,
    payment_id: int,
    status: PaymentStatus,
) -> Optional[Payment]:
    """Update payment status."""
    payment = await session.get(Payment, payment_id)
    if payment:
        payment.status = status
        if status == PaymentStatus.COMPLETED:
            payment.completed_at = datetime.now()
        await session.commit()
        await session.refresh(payment)
    return payment


async def get_user_payments(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> List[Payment]:
    """Get user's payment history."""
    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ============================================================================
# SUPPORT TICKET CRUD
# ============================================================================

async def get_user_tickets(
    session: AsyncSession,
    user_id: int,
    status: Optional[TicketStatus] = None,
    limit: int = 20,
) -> List[SupportTicket]:
    """Get user's support tickets."""
    query = select(SupportTicket).where(SupportTicket.user_id == user_id)

    if status:
        query = query.where(SupportTicket.status == status)

    query = query.order_by(SupportTicket.created_at.desc()).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def count_open_tickets(
    session: AsyncSession,
    user_id: int,
) -> int:
    """Count user's open tickets."""
    result = await session.execute(
        select(func.count(SupportTicket.id))
        .where(SupportTicket.user_id == user_id)
        .where(SupportTicket.status == TicketStatus.OPEN)
    )
    return result.scalar() or 0


async def create_support_ticket(
    session: AsyncSession,
    user_id: int,
    category: str,
    priority: str,
    title: str,
    description: str,
) -> SupportTicket:
    """Create new support ticket."""
    ticket = SupportTicket(
        user_id=user_id,
        category=category,
        priority=priority,
        status=TicketStatus.OPEN,
        title=title,
        description=description,
    )

    session.add(ticket)
    await session.flush()
    return ticket


async def get_ticket_by_id(
    session: AsyncSession,
    ticket_id: int,
) -> Optional[SupportTicket]:
    """Get ticket with messages."""
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def update_ticket_status(
    session: AsyncSession,
    ticket_id: int,
    status: TicketStatus,
) -> Optional[SupportTicket]:
    """Update ticket status."""
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket:
        ticket.status = status
        if status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.now()
        await session.commit()
        await session.refresh(ticket)
    return ticket


async def add_ticket_message(
    session: AsyncSession,
    ticket_id: int,
    user_id: int,
    message: str,
    is_admin: bool = False,
) -> TicketMessage:
    """Add message to ticket."""
    ticket_message = TicketMessage(
        ticket_id=ticket_id,
        user_id=user_id,
        message=message,
        is_admin=is_admin,
    )

    session.add(ticket_message)
    await session.flush()
    return ticket_message


async def get_ticket_messages(
    session: AsyncSession,
    ticket_id: int,
) -> List[TicketMessage]:
    """Get all messages for a ticket."""
    result = await session.execute(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
    )
    return list(result.scalars().all())


# ============================================================================
# REFERRAL CRUD
# ============================================================================

async def create_referral(
    session: AsyncSession,
    referrer_id: int,
    referred_id: int,
    bonus_amount: Decimal = Decimal("1.00"),
) -> Referral:
    """Create new referral."""
    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
        bonus_amount=bonus_amount,
        status=ReferralStatus.PENDING,
    )

    session.add(referral)
    await session.flush()
    return referral


async def get_referral_by_referred_id(
    session: AsyncSession,
    referred_id: int,
) -> Optional[Referral]:
    """Get referral by referred user ID."""
    result = await session.execute(
        select(Referral).where(Referral.referred_id == referred_id)
    )
    return result.scalar_one_or_none()


async def get_user_referrals(
    session: AsyncSession,
    referrer_id: int,
    status: Optional[ReferralStatus] = None,
) -> List[Referral]:
    """Get user's referrals."""
    query = select(Referral).where(Referral.referrer_id == referrer_id)

    if status:
        query = query.where(Referral.status == status)

    query = query.order_by(Referral.created_at.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_referral_stats(
    session: AsyncSession,
    referrer_id: int,
) -> dict:
    """Get referral statistics for user."""
    total = await session.execute(
        select(func.count(Referral.id))
        .where(Referral.referrer_id == referrer_id)
    )
    total_referrals = total.scalar() or 0

    active = await session.execute(
        select(func.count(Referral.id))
        .where(Referral.referrer_id == referrer_id)
        .where(Referral.status == ReferralStatus.ACTIVE)
    )
    active_referrals = active.scalar() or 0

    # Calculate total earned
    result = await session.execute(
        select(func.sum(Referral.bonus_amount))
        .where(Referral.referrer_id == referrer_id)
        .where(Referral.status == ReferralStatus.ACTIVE)
    )
    total_earned = result.scalar() or Decimal("0")

    return {
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        "total_earned": float(total_earned),
    }


async def activate_referral(
    session: AsyncSession,
    referral_id: int,
    payment_id: int,
) -> Optional[Referral]:
    """Activate referral after payment."""
    referral = await session.get(Referral, referral_id)
    if referral:
        referral.status = ReferralStatus.ACTIVE
        referral.payment_id = payment_id
        referral.activated_at = datetime.now()
        await session.commit()
        await session.refresh(referral)
    return referral


# ============================================================================
# INVITE CRUD (Legacy v3.x)
# ============================================================================

async def get_invite_by_code(
    session: AsyncSession,
    code: str,
) -> Optional[Invite]:
    """Get invite by code."""
    result = await session.execute(
        select(Invite).where(Invite.code == code)
    )
    return result.scalar_one_or_none()


async def validate_invite_code(
    session: AsyncSession,
    code: str,
) -> Optional[Invite]:
    """
    Validate invite code.

    Checks:
    - Code exists
    - Is active
    - Not expired
    - Has remaining uses
    """
    invite = await get_invite_by_code(session, code)

    if not invite:
        return None

    # Check if active
    if not invite.is_active:
        return None

    # Check expiration
    if invite.expires_at and invite.expires_at < datetime.now():
        return None

    # Check usage limit
    if invite.used_count >= invite.max_uses:
        return None

    return invite


async def use_invite_code(
    session: AsyncSession,
    code: str,
) -> Optional[Invite]:
    """
    Use invite code (atomically).

    Increments used_count and deactivates if limit reached.
    """
    invite = await validate_invite_code(session, code)

    if not invite:
        return None

    # Increment used count
    invite.used_count += 1

    # Deactivate if limit reached
    if invite.used_count >= invite.max_uses:
        invite.is_active = False

    await session.commit()
    await session.refresh(invite)

    return invite


async def create_invite_code(
    session: AsyncSession,
    code: str,
    created_by: int,
    max_uses: int = 1,
    expires_at: Optional[datetime] = None,
) -> Invite:
    """Create new invite code."""
    invite = Invite(
        code=code,
        created_by=created_by,
        max_uses=max_uses,
        expires_at=expires_at,
    )

    session.add(invite)
    await session.flush()
    return invite
