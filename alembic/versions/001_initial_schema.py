"""Initial schema for Hiddify Bot v4.0

Revision ID: 001
Revises:
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger(), unique=True, nullable=False),
        sa.Column('username', sa.String(255)),
        sa.Column('first_name', sa.String(255)),
        sa.Column('last_name', sa.String(255)),
        sa.Column('role', sa.String(), default='user'),
        sa.Column('invite_code', sa.String(), unique=True),
        sa.Column('invited_by', sa.BigInteger()),
        sa.Column('data_limit_bytes', sa.BigInteger()),
        sa.Column('used_bytes', sa.BigInteger(), default=0),
        sa.Column('expires_at', sa.TIMESTAMP()),
        sa.Column('is_trial', sa.Boolean(), default=False),
        sa.Column('trial_expiry', sa.TIMESTAMP()),
        sa.Column('trial_activated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP(), default=sa.func.current_timestamp())
    )

    # Create invites table
    op.create_table(
        'invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(), unique=True, nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('max_uses', sa.Integer(), default=1, nullable=False),
        sa.Column('used_count', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('expires_at', sa.TIMESTAMP()),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp())
    )

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('plan_code', sa.String(50), nullable=False),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('started_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('auto_renew', sa.Boolean(), default=False),
        sa.Column('data_limit_bytes', sa.BigInteger()),
        sa.Column('used_bytes', sa.BigInteger(), default=0),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['user_id'], ['users.telegram_id'])
    )

    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.String(), unique=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('checkout_url', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.Column('paid_at', sa.TIMESTAMP()),
        sa.ForeignKeyConstraint(['user_id'], ['users.telegram_id'])
    )

    # Create support_tickets table
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(), default='open'),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(), default='normal'),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.Column('resolved_at', sa.TIMESTAMP()),
        sa.Column('admin_notes', sa.Text()),
        sa.ForeignKeyConstraint(['user_id'], ['users.telegram_id'])
    )

    # Create ticket_messages table
    op.create_table(
        'ticket_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'])
    )

    # Create referrals table
    op.create_table(
        'referrals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('referrer_id', sa.BigInteger(), nullable=False),
        sa.Column('referred_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.Column('bonus_amount', sa.Numeric(10, 2), default=0),
        sa.Column('status', sa.String(), default='pending'),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.telegram_id']),
        sa.ForeignKeyConstraint(['referred_id'], ['users.telegram_id']),
        sa.UniqueConstraint('referred_id')
    )

    # Create promo_codes table
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(), unique=True, nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('value', sa.Numeric(10, 2), nullable=False),
        sa.Column('max_uses', sa.Integer()),
        sa.Column('used_count', sa.Integer(), default=0),
        sa.Column('expires_at', sa.TIMESTAMP()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_by', sa.BigInteger()),
        sa.Column('created_at', sa.TIMESTAMP(), default=sa.func.current_timestamp())
    )

    # Create promo_usage table
    op.create_table(
        'promo_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('promo_code_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(), default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['promo_code_id'], ['promo_codes.id']),
        sa.UniqueConstraint('promo_code_id', 'user_id')
    )

    # Create indexes
    op.create_index('idx_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_invited_by', 'users', ['invited_by'])
    op.create_index('idx_invites_code', 'invites', ['code'])
    op.create_index('idx_invites_created_by', 'invites', ['created_by'])
    op.create_index('idx_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('idx_payments_user_id', 'payments', ['user_id'])
    op.create_index('idx_payments_status', 'payments', ['status'])
    op.create_index('idx_payments_provider_id', 'payments', ['provider_id'])
    op.create_index('idx_tickets_user_id', 'support_tickets', ['user_id'])
    op.create_index('idx_tickets_status', 'support_tickets', ['status'])
    op.create_index('idx_ticket_messages_ticket_id', 'ticket_messages', ['ticket_id'])
    op.create_index('idx_referrals_referrer_id', 'referrals', ['referrer_id'])
    op.create_index('idx_referrals_referred_id', 'referrals', ['referred_id'])


def downgrade() -> None:
    op.drop_table('promo_usage')
    op.drop_table('promo_codes')
    op.drop_table('referrals')
    op.drop_table('ticket_messages')
    op.drop_table('support_tickets')
    op.drop_table('payments')
    op.drop_table('subscriptions')
    op.drop_table('invites')
    op.drop_table('users')
