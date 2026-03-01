"""
FSM States for Hiddify Bot.
All user conversation states for aiogram 3 FSM.
"""

from aiogram.fsm.state import State, StatesGroup


# ============================================================================
# USER STATES
# ============================================================================

class UserStates(StatesGroup):
    """Basic user states."""
    menu = State()


# ============================================================================
# CREATE USER STATES (Admin)
# ============================================================================

class CreateUserStates(StatesGroup):
    """Admin creating new user flow."""
    username = State()
    confirm = State()


# ============================================================================
# GET KEY STATES
# ============================================================================

class GetKeyStates(StatesGroup):
    """User getting VPN key flow."""
    select_protocol = State()
    select_platform = State()


# ============================================================================
# TRIAL ACTIVATION STATES
# ============================================================================

class TrialStates(StatesGroup):
    """Trial activation flow."""
    confirming = State()


# ============================================================================
# PAYMENT STATES
# ============================================================================

class PaymentStates(StatesGroup):
    """Payment flow for subscription."""
    select_plan = State()
    select_method = State()
    entering_promo = State()
    processing = State()


# ============================================================================
# SUPPORT TICKET STATES
# ============================================================================

class TicketStates(StatesGroup):
    """Support ticket creation flow."""
    select_category = State()
    enter_title = State()
    enter_description = State()


# ============================================================================
# ADMIN USER MANAGEMENT STATES
# ============================================================================

class AdminUserStates(StatesGroup):
    """Admin user management flow."""
    select_action = State()
    extend_subscription = State()
    set_limit = State()
    block_user = State()


# ============================================================================
# REFERRAL STATES
# ============================================================================

class ReferralStates(StatesGroup):
    """Referral system flow."""
    showing_link = State()
    showing_stats = State()


# ============================================================================
# INVITE CODE STATES (Legacy v3.x)
# ============================================================================

class InviteStates(StatesGroup):
    """Invite code management flow."""
    create_code = State()
    set_max_uses = State()
    set_expiry = State()


# ============================================================================
# SETTINGS STATES
# ============================================================================

class SettingsStates(StatesGroup):
    """User settings flow."""
    main = State()
    change_protocol = State()
