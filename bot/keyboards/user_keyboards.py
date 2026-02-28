"""
Keyboards for Hiddify Bot.
All reply and inline keyboards for user interaction.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# ============================================================================
# REPLY KEYBOARDS (Главное меню)
# ============================================================================

def get_user_main_keyboard(
    has_subscription: bool = False,
    trial_available: bool = False,
    show_referral: bool = True,
) -> ReplyKeyboardMarkup:
    """
    Главная клавиатура пользователя.

    Args:
        has_subscription: Есть ли активная подписка
        trial_available: Доступен ли trial
        show_referral: Показывать ли кнопку реферальной программы
    """
    builder = ReplyKeyboardBuilder()

    # Основные кнопки
    builder.add(
        KeyboardButton(text="📱 Мои устройства"),
        KeyboardButton(text="🔗 Получить ключ"),
    )
    builder.row(
        KeyboardButton(text="📊 Моя подписка"),
        KeyboardButton(text="💬 Поддержка"),
    )

    # Trial кнопка
    if trial_available:
        builder.row(KeyboardButton(text="🎁 Пробный период"))

    # Реферальная программа
    if show_referral:
        builder.row(KeyboardButton(text="👥 Пригласить друга"))

    # Кнопка настроек
    builder.row(KeyboardButton(text="⚙️ Настройки"))

    return builder.as_markup(resize_keyboard=True)


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура админа."""
    builder = ReplyKeyboardBuilder()

    builder.add(
        KeyboardButton(text="👥 Пользователи"),
        KeyboardButton(text="➕ Создать юзера"),
    )
    builder.row(
        KeyboardButton(text="📈 Статистика"),
        KeyboardButton(text="🎫 Инвайты"),
    )
    builder.row(
        KeyboardButton(text="💬 Тикеты поддержки"),
        KeyboardButton(text="📊 Рассылка"),
    )
    builder.row(KeyboardButton(text="⚙️ Настройки"))

    return builder.as_markup(resize_keyboard=True)


# ============================================================================
# INLINE KEYBOARDS - Протоколы
# ============================================================================

def get_protocol_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура выбора протокола (VLESS Reality only)."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ VLESS Reality ⭐ (Рекомендуется)",
            callback_data="protocol_vless_reality"
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))

    return builder.as_markup()


def get_platform_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура выбора платформы."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📱 iOS", callback_data="platform_ios"),
        InlineKeyboardButton(text="🤖 Android", callback_data="platform_android"),
    )
    builder.row(
        InlineKeyboardButton(text="🪟 Windows", callback_data="platform_windows"),
        InlineKeyboardButton(text="💻 macOS", callback_data="platform_macos"),
    )
    builder.row(
        InlineKeyboardButton(text="🐧 Linux", callback_data="platform_linux"),
        InlineKeyboardButton(text="🌐 Web", callback_data="platform_web"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Подписка и оплата
# ============================================================================

def get_trial_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура активации trial."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🎁 Активировать пробный период", callback_data="activate_trial")
    )

    return builder.as_markup()


def get_buy_subscription_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура покупки подписки."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription")
    )

    return builder.as_markup()


def get_subscription_plans_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура выбора плана подписки."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📅 Неделя - $3.00", callback_data="plan_weekly")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Месяц - $10.00", callback_data="plan_monthly")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Квартал - $25.00", callback_data="plan_quarterly")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment"))

    return builder.as_markup()


def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура выбора способа оплаты."""
    builder = InlineKeyboardBuilder()

    # CryptoBot
    builder.row(
        InlineKeyboardButton(text="💳 CryptoBot (USDT)", callback_data="pay_cryptobot")
    )

    # Telegram Stars
    builder.row(
        InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="pay_stars")
    )

    # YooMoney (опционально)
    # builder.row(
    #     InlineKeyboardButton(text="💳 ЮМани", callback_data="pay_yoomoney")
    # )

    # Промокод
    builder.row(
        InlineKeyboardButton(text="🎫 Промокод", callback_data="pay_promo")
    )

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy_subscription"))

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Реферальная программа
# ============================================================================

def get_referral_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура реферальной программы."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📤 Скопировать", callback_data="invite_copy")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Отправить", url="https://t.me/share/url?url=")  # URL will be set dynamically
    )

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Поддержка
# ============================================================================

def get_support_categories_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура выбора категории тикета."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Оплата", callback_data="ticket_category_payment")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Подключение", callback_data="ticket_category_connection")
    )
    builder.row(
        InlineKeyboardButton(text="📶 Скорость", callback_data="ticket_category_speed")
    )
    builder.row(
        InlineKeyboardButton(text="👤 Аккаунт", callback_data="ticket_category_account")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Другое", callback_data="ticket_category_other")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))

    return builder.as_markup()


def get_ticket_actions_keyboard(ticket_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Inline клавиатура действий с тикетом.

    Args:
        ticket_id: ID тикета
        is_admin: Является ли пользователь администратором
    """
    builder = InlineKeyboardBuilder()

    if is_admin:
        builder.row(
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"ticket_reply_{ticket_id}"),
            InlineKeyboardButton(text="✅ Решено", callback_data=f"ticket_resolve_{ticket_id}"),
        )
        builder.row(
            InlineKeyboardButton(text="❌ Закрыть", callback_data=f"ticket_close_{ticket_id}"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="💬 Добавить сообщение", callback_data=f"ticket_message_{ticket_id}"),
        )
        builder.row(
            InlineKeyboardButton(text="❌ Закрыть", callback_data=f"ticket_close_user_{ticket_id}"),
        )

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Admin управление пользователями
# ============================================================================

def get_admin_user_inline_keyboard(user_id: int, username: str = None) -> InlineKeyboardMarkup:
    """
    Inline клавиатура управления пользователем.

    Args:
        user_id: ID пользователя
        username: Username пользователя
    """
    builder = InlineKeyboardBuilder()

    # Основные действия
    builder.row(
        InlineKeyboardButton(text="🔑 Продлить", callback_data=f"user_extend_{user_id}"),
        InlineKeyboardButton(text="📦 Лимит", callback_data=f"user_limit_{user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"user_unblock_{user_id}"),
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"user_block_{user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"user_stats_{user_id}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close"))

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Инвайты (админ)
# ============================================================================

def get_invite_management_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура управления инвайтами."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="➕ Создать инвайт", callback_data="invite_create")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список инвайтов", callback_data="invite_list")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="invite_stats")
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close"))

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Отмена операций
# ============================================================================

def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура с кнопкой отмены."""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))

    return builder.as_markup()


def get_confirm_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура подтверждения/отмены."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_operation"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"),
    )

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Инструкции и помощь
# ============================================================================

def get_troubleshoot_keyboard(platform: str) -> InlineKeyboardMarkup:
    """
    Inline клавиатура решения проблем.

    Args:
        platform: Платформа (ios, android, etc.)
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔧 Решение проблем", callback_data=f"troubleshoot_{platform}")
    )
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="help"))

    return builder.as_markup()


def get_back_inline_keyboard(callback_data: str = "menu") -> InlineKeyboardMarkup:
    """
    Inline клавиатура с кнопкой "Назад".

    Args:
        callback_data: Callback data для кнопки "Назад"
    """
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data))

    return builder.as_markup()


# ============================================================================
# INLINE KEYBOARDS - Настройки
# ============================================================================

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура настроек."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔧 Протоколы", callback_data="settings_protocols")
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Язык", callback_data="settings_language")
    )
    builder.row(
        InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications")
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_settings"))

    return builder.as_markup()


def get_protocol_selection_keyboard(current_protocols: dict) -> InlineKeyboardMarkup:
    """
    Inline клавиатура выбора активных протоколов (VLESS Reality only).

    Args:
        current_protocols: Текущий статус протоколов
            {"vless_reality": True}
    """
    builder = InlineKeyboardBuilder()

    vless_text = "✅ VLESS Reality" if current_protocols.get("vless_reality") else "☐ VLESS Reality"

    builder.row(
        InlineKeyboardButton(text=vless_text, callback_data="toggle_vless_reality")
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_settings"))

    return builder.as_markup()
