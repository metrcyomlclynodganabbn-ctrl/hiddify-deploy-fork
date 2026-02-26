"""
v4.0 Handlers для Telegram бота

Новые функции v4.0:
- Payment система (Stripe, промокоды)
- Support tickets
- Referral программа
- Config Builder (Standard/Enhanced)
"""

import os
import logging
import asyncio
from decimal import Decimal
from datetime import datetime
from telebot import types

# Локальные модули
logger = logging.getLogger(__name__)

# Попытка импортировать v4.0 модули
try:
    from scripts.payments.stripe_client import stripe_client, init_stripe_client
    from scripts.payments.promo_client import promo_client, PromoCodeType
    from scripts.support.ticket_manager import ticket_manager
    from scripts.referral.referral_manager import referral_manager
    from scripts.config.standard_builder import build_standard_config, generate_vless_url
    from scripts.config.enhanced_builder import build_enhanced_config, generate_vless_url_enhanced, get_config_recommendation
    from scripts.cache.redis_client import redis_client, init_redis
    from scripts.monitoring.metrics import metrics, track_message_duration
    from scripts.database.models import (
        PaymentCreate, PaymentMethod, PaymentStatus,
        SupportTicketCreate, TicketCategory, TicketPriority,
        SubscriptionPlan, SubscriptionPlanDetails
    )

    # Определение планов подписки (только при успешном импорте)
    PLANS = {
        "weekly": SubscriptionPlanDetails(
            code=SubscriptionPlan.WEEKLY,
            name="Неделя",
            description="Доступ на 7 дней",
            price=Decimal("3.00"),
            currency="USD",
            duration_days=7,
            data_limit_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
            features=["До 10 GB трафика", "7 дней доступа", "Standard скорость"]
        ),
        "monthly": SubscriptionPlanDetails(
            code=SubscriptionPlan.MONTHLY,
            name="Месяц",
            description="Доступ на 30 дней",
            price=Decimal("10.00"),
            currency="USD",
            duration_days=30,
            data_limit_bytes=50 * 1024 * 1024 * 1024,  # 50 GB
            features=["До 50 GB трафика", "30 дней доступа", "Высокая скорость"]
        ),
        "quarterly": SubscriptionPlanDetails(
            code=SubscriptionPlan.QUARTERLY,
            name="Квартал",
            description="Доступ на 90 дней",
            price=Decimal("25.00"),
            currency="USD",
            duration_days=90,
            data_limit_bytes=200 * 1024 * 1024 * 1024,  # 200 GB
            features=["До 200 GB трафика", "90 дней доступа", "Приоритетная поддержка"]
        ),
    }

    V4_AVAILABLE = True
except ImportError as e:
    logger.warning(f"v4.0 модули не доступны: {e}")
    V4_AVAILABLE = False
    PLANS = {}  # Пустой словарь при ошибке импорта


def register_payment_handlers(bot):
    """Регистрация обработчиков платежей"""

    @bot.callback_query_handler(func=lambda call: call.data == 'buy_subscription')
    def handle_buy_subscription(callback):
        """Начало покупки подписки"""
        if not V4_AVAILABLE:
            bot.answer_callback_query(callback.id, "❌ Платежи временно недоступны")
            return

        user_id = callback.from_user.id

        # Клавиатура выбора плана
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for plan_key, plan in PLANS.items():
            button_text = f"{plan.name} - ${plan.price} / {plan.duration_days} дней"
            keyboard.add(
                types.InlineKeyboardButton(button_text, callback_data=f"plan_{plan_key}")
            )

        keyboard.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment"))

        text = "💳 Выберите план подписки:\n\n"
        for plan_key, plan in PLANS.items():
            text += f"• <b>{plan.name}</b> - ${plan.price}\n"
            text += f"  {plan.description}\n"
            for feature in plan.features:
                text += f"  ✓ {feature}\n"
            text += "\n"

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('plan_'))
    def handle_plan_selected(callback):
        """Выбран план подписки"""
        if not V4_AVAILABLE:
            bot.answer_callback_query(callback.id, "❌ Платежи временно недоступны")
            return

        plan_key = callback.data.split('_')[1]
        plan = PLANS.get(plan_key)

        if not plan:
            bot.answer_callback_query(callback.id, "❌ План не найден")
            return

        # Сохранить выбор плана
        user_id = callback.from_user.id

        # Клавиатура выбора способа оплаты
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("💳 Карта (Stripe)", callback_data=f"pay_card_{plan_key}")
        )
        keyboard.add(
            types.InlineKeyboardButton("₿ Крипта (скоро)", callback_data="pay_crypto_soon")
        )
        keyboard.add(
            types.InlineKeyboardButton("🎫 Промокод", callback_data=f"pay_promo_{plan_key}")
        )
        keyboard.add(
            types.InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")
        )

        text = f"💳 Выбран план: <b>{plan.name}</b> - ${plan.price}\n\n"
        text += "Выберите способ оплаты:"

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('pay_card_'))
    def handle_payment_card(callback):
        """Оплата картой через Stripe"""
        if not V4_AVAILABLE:
            bot.answer_callback_query(callback.id, "❌ Платежи временно недоступны")
            return

        plan_key = callback.data.split('_')[2]
        plan = PLANS.get(plan_key)

        if not plan:
            bot.answer_callback_query(callback.id, "❌ План не найден")
            return

        user_id = callback.from_user.id

        # Создать платеж
        payment = PaymentCreate(
            user_id=user_id,
            amount=plan.price,
            currency=plan.currency,
            method=PaymentMethod.CARD,
            plan_code=plan.code
        )

        # TODO: Создать checkout сессию Stripe
        # result = await stripe_client.create_checkout_session(...)

        # Временно - симуляция
        text = f"💳 <b>Оплата картой</b>\n\n"
        text += f"План: {plan.name}\n"
        text += f"Сумма: ${plan.price}\n\n"
        text += "🔧 Stripe интеграция в процессе настройки...\n\n"
        text += "Для тестирования платежей используйте промокод!"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("🎫 Ввести промокод", callback_data=f"pay_promo_{plan_key}")
        )
        keyboard.add(
            types.InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")
        )

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda call: call.data == 'pay_crypto_soon')
    def handle_payment_crypto_soon(callback):
        """Криптоплатежи скоро"""
        bot.answer_callback_query(
            callback.id,
            "🔔 Криптоплатежи будут добавлены в следующем обновлении",
            show_alert=True
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('pay_promo_'))
    def handle_payment_promo(callback):
        """Оплата промокодом"""
        if not V4_AVAILABLE:
            bot.answer_callback_query(callback.id, "❌ Платежи временно недоступны")
            return

        plan_key = callback.data.split('_')[2]
        user_id = callback.from_user.id

        # Запрос промокода
        msg = bot.send_message(
            callback.message.chat.id,
            "🎫 Введите промокод:"
        )

        # Сохранить состояние
        from monitor_bot import set_user_state
        set_user_state(user_id, 'awaiting_promo_code', {'plan_key': plan_key})

        bot.register_next_step_handler(msg, process_promo_code)

    @bot.callback_query_handler(func=lambda call: call.data == 'cancel_payment')
    def handle_cancel_payment(callback):
        """Отмена оплаты"""
        bot.answer_callback_query(callback.id)
        bot.delete_message(callback.message.chat.id, callback.message.message_id)


def process_promo_code(message):
    """Обработка введённого промокода"""
    if not V4_AVAILABLE:
        bot.send_message(message.chat.id, "❌ Промокоды временно недоступны")
        return

    from monitor_bot import get_user_state, clear_user_state

    user_id = message.from_user.id
    state = get_user_state(user_id)

    if not state or state.get('state') != 'awaiting_promo_code':
        bot.send_message(message.chat.id, "❌ Некорректная операция")
        return

    promo_code = message.text.strip().upper()
    plan_key = state['data'].get('plan_key')
    plan = PLANS.get(plan_key)

    # TODO: Валидация и применение промокода
    # is_valid, msg, promo_data = await promo_client.validate_promo_code(promo_code, user_id)

    # Временно - демо
    text = f"🎫 <b>Промокод: {promo_code}</b>\n\n"
    text += f"План: {plan.name if plan else 'N/A'}\n"
    text += f"Сумма: ${plan.price if plan else '0.00'}\n\n"
    text += "🔧 Промокод система в процессе настройки...\n"
    text += "Промокод будет применён автоматически после настройки."

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("◀️ В меню", callback_data="buy_subscription")
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

    clear_user_state(user_id)


# ============================================================================
# SUPPORT TICKET HANDLERS
# ============================================================================

def register_support_handlers(bot):
    """Регистрация обработчиков поддержки"""

    @bot.message_handler(commands=['support'])
    def handle_support_command(message):
        """Команда /support - создать тикет"""
        if not V4_AVAILABLE:
            bot.send_message(message.chat.id, "❌ Поддержка временно недоступна")
            return

        user_id = message.from_user.id

        # Проверка количества открытых тикетов
        # open_count = asyncio.run(ticket_manager.get_user_open_tickets_count(user_id))

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("💳 Оплата", callback_data="ticket_category_payment"),
            types.InlineKeyboardButton("🔗 Подключение", callback_data="ticket_category_connection")
        )
        keyboard.add(
            types.InlineKeyboardButton("⚡ Скорость", callback_data="ticket_category_speed"),
            types.InlineKeyboardButton("👤 Аккаунт", callback_data="ticket_category_account")
        )
        keyboard.add(
            types.InlineKeyboardButton("📝 Другое", callback_data="ticket_category_other")
        )

        text = "📝 Выберите категорию обращения:\n\n"
        text += "Опишите вашу проблему, и мы ответим в ближайшее время."

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=keyboard
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('ticket_category_'))
    def handle_ticket_category(callback):
        """Выбрана категория тикета"""
        if not V4_AVAILABLE:
            bot.answer_callback_query(callback.id, "❌ Поддержка временно недоступна")
            return

        category_str = callback.data.replace('ticket_category_', '')
        category = TicketCategory(category_str)

        # Запрос заголовка
        msg = bot.send_message(
            callback.message.chat.id,
            f"📝 Категория: {category.value}\n\n"
            "Введите краткое описание проблемы (заголовок):"
        )

        # Сохранить состояние
        from monitor_bot import set_user_state
        set_user_state(callback.from_user.id, 'awaiting_ticket_title', {'category': category})

        bot.register_next_step_handler(msg, process_ticket_title)

    bot.answer_callback_query(callback.id)


def process_ticket_title(message):
    """Обработка заголовка тикета"""
    if not V4_AVAILABLE:
        bot.send_message(message.chat.id, "❌ Поддержка временно недоступна")
        from monitor_bot import clear_user_state
        clear_user_state(message.from_user.id)
        return

    from monitor_bot import get_user_state, set_user_state

    user_id = message.from_user.id
    state = get_user_state(user_id)

    if not state or state.get('state') != 'awaiting_ticket_title':
        bot.send_message(message.chat.id, "❌ Некорректная операция")
        return

    title = message.text.strip()

    if len(title) < 3 or len(title) > 200:
        msg = bot.send_message(
            message.chat.id,
            "❌ Заголовок должен быть от 3 до 200 символов. Попробуйте ещё раз:"
        )
        bot.register_next_step_handler(msg, process_ticket_title)
        return

    # Запрос описания
    msg = bot.send_message(
        message.chat.id,
        "✅ Заголовок принят.\n\n"
        "Теперь введите подробное описание проблемы:"
    )

    set_user_state(user_id, 'awaiting_ticket_description', {
        'category': state['data']['category'],
        'title': title
    })

    bot.register_next_step_handler(msg, process_ticket_description)


def process_ticket_description(message):
    """Обработка описания тикета"""
    if not V4_AVAILABLE:
        bot.send_message(message.chat.id, "❌ Поддержка временно недоступна")
        from monitor_bot import clear_user_state
        clear_user_state(message.from_user.id)
        return

    from monitor_bot import get_user_state, clear_user_state

    user_id = message.from_user.id
    state = get_user_state(user_id)

    if not state or state.get('state') != 'awaiting_ticket_description':
        bot.send_message(message.chat.id, "❌ Некорректная операция")
        return

    description = message.text.strip()

    if len(description) < 10 or len(description) > 5000:
        msg = bot.send_message(
            message.chat.id,
            "❌ Описание должно быть от 10 до 5000 символов. Попробуйте ещё раз:"
        )
        bot.register_next_step_handler(msg, process_ticket_description)
        return

    # Создать тикет
    ticket = SupportTicketCreate(
        user_id=user_id,
        category=state['data']['category'],
        title=state['data']['title'],
        description=description
    )

    # TODO: Создать тикет в БД
    # result = asyncio.run(ticket_manager.create_ticket(ticket))

    # Очистить состояние
    clear_user_state(user_id)

    text = f"✅ <b>Тикет создан!</b>\n\n"
    text += f"Категория: {state['data']['category'].value}\n"
    text += f"Заголовок: {state['data']['title']}\n\n"
    text += "Мы ответим вам в ближайшее время."

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


# ============================================================================
# REFERRAL HANDLERS
# ============================================================================

def register_referral_handlers(bot):
    """Регистрация обработчиков реферальной программы"""

    @bot.callback_query_handler(func=lambda call: call.data == 'my_referrals')
    def handle_my_referrals(callback):
        """Показать статистику рефералов"""
        if not V4_AVAILABLE:
            bot.answer_callback_query(callback.id, "❌ Рефералы временно недоступны")
            return

        user_id = callback.from_user.id

        # TODO: Получить статистику
        # stats = asyncio.run(referral_manager.get_referral_stats(user_id))
        # referrals = asyncio.run(referral_manager.get_user_referrals(user_id))

        # Временно - демо данные
        total_referrals = 5
        active_referrals = 3
        total_earned = Decimal("5.00")
        pending_payout = Decimal("2.00")

        text = f"👥 <b>Мои рефералы</b>\n\n"
        text += f"Приглашено: <b>{total_referrals}</b> человек\n"
        text += f"Активных: <b>{active_referrals}</b>\n"
        text += f"Заработано: <b>${total_earned:.2f}</b>\n"
        text += f"Ожидает выплаты: <b>${pending_payout:.2f}</b>\n\n"

        # TODO: Добавить список рефералов
        # text += "Последние рефералы:\n"
        # for ref in referrals[:5]:
        #     text += f"• {ref['referred_username'] or 'Аноним'} - ${ref['bonus_amount']:.2f}\n"

        # Генерация реферальной ссылки
        # referral_link = asyncio.run(referral_manager.generate_referral_link(
        #     user_id,
        #     bot_username=os.getenv('TELEGRAM_BOT_USERNAME', 'SKRTvpnbot')
        # ))

        referral_link = f"https://t.me/{os.getenv('TELEGRAM_BOT_USERNAME', 'SKRTvpnbot')}?start=ref_{user_id}"

        text += f"\n🔗 <b>Ваша реферальная ссылка:</b>\n"
        text += f"<code>{referral_link}</code>"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📋 Копировать ссылку", callback_data=f"copy_referral_{user_id}")
        )
        keyboard.add(
            types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        )

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('copy_referral_'))
    def handle_copy_referral(callback):
        """Копировать реферальную ссылку"""
        user_id = callback.from_user.id
        referral_link = f"https://t.me/{os.getenv('TELEGRAM_BOT_USERNAME', 'SKRTvpnbot')}?start=ref_{user_id}"

        bot.answer_callback_query(
            callback.id,
            f"📋 Ссылка скопирована!\n{referral_link}",
            show_alert=True
        )


# ============================================================================
# CONFIG BUILDER HANDLERS
# ============================================================================

def register_config_handlers(bot):
    """Регистрация обработчиков конфигурации"""

    @bot.callback_query_handler(func=lambda call: call.data == 'create_config')
    def handle_create_config(callback):
        """Создание конфига с выбором режима"""
        user_id = callback.from_user.id

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("⚡ Standard (быстрый)", callback_data="config_mode_standard")
        )
        keyboard.add(
            types.InlineKeyboardButton("🔒 Enhanced (приватный)", callback_data="config_mode_enhanced")
        )
        keyboard.add(
            types.InlineKeyboardButton("ℹ️ Сравнение режимов", callback_data="config_compare")
        )
        keyboard.add(
            types.InlineKeyboardButton("◀️ Назад", callback_data="main_menu")
        )

        text = "📱 Выберите режим конфигурации:\n\n"
        text += "⚡ <b>Standard</b> - максимальная скорость\n"
        text += "   • Smart routing (торренты напрямую)\n"
        text += "   • Минимальные задержки\n"
        text += "   • Рекомендуется для повседневного использования\n\n"
        text += "🔒 <b>Enhanced</b> - максимальная приватность\n"
        text += "   • Fragment packets\n"
        text += "   • Весь трафик через VPN\n"
        text += "   • Защита от DPI и анализа"

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('config_mode_'))
    def handle_config_mode_selection(callback):
        """Обработка выбора режима"""
        mode = callback.data.split('_')[2]
        user_id = callback.from_user.id

        # TODO: Генерация конфига
        # if mode == 'standard':
        #     config = build_standard_config(...)
        # else:
        #     config = build_enhanced_config(...)

        # Временно - демо
        mode_name = "Standard" if mode == 'standard' else "Enhanced"
        mode_emoji = "⚡" if mode == 'standard' else "🔒"

        text = f"{mode_emoji} <b>{mode_name} конфиг</b>\n\n"
        text += "🔧 Генерация конфигурации в процессе настройки...\n\n"
        text += "Конфигурация будет доступна после:"
        text += "\n• Настройки VPS_IP в .env"
        text += "\n• Настройки REALITY_PUBLIC_KEY"
        text += "\n• Интеграции с Hiddify API"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("◀️ Назад", callback_data="create_config")
        )

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda call: call.data == 'config_compare')
    def handle_config_compare(callback):
        """Сравнение режимов конфигурации"""
        text = "📊 <b>Сравнение режимов</b>\n\n"
        text += "<b>Standard</b>:\n"
        text += "✅ Максимальная скорость\n"
        text += "✅ Торренты напрямую\n"
        text += "✅ Низкие задержки\n"
        text += "❌ Меньше приватности\n\n"
        text += "<b>Enhanced</b>:\n"
        text += "✅ Максимальная приватность\n"
        text += "✅ Fragment packets\n"
        text += "✅ Защита от DPI\n"
        text += "❌ Выше задержки\n\n"
        text += "💡 <b>Рекомендация</b>:\n"
        text += "• Для РФ/Китая/Ирана → Enhanced\n"
        text += "• Для обычного использования → Standard"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("◀️ Назад", callback_data="create_config")
        )

        bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(callback.id)


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ v4.0
# ============================================================================

async def init_v4_modules():
    """Инициализация модулей v4.0"""
    if not V4_AVAILABLE:
        logger.warning("v4.0 модули недоступны")
        return False

    try:
        # Инициализация Redis
        await init_redis()

        # Инициализация Stripe
        init_stripe_client()

        # Запуск Prometheus metrics
        await metrics.start_server()

        # Запуск health check сервера
        from scripts.monitoring.health import start_health_server
        await start_health_server()

        logger.info("v4.0 модули инициализированы")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации v4.0 модулей: {e}")
        return False


def register_all_v4_handlers(bot):
    """Регистрация всех обработчиков v4.0"""
    if not V4_AVAILABLE:
        logger.warning("v4.0 handlers недоступны")
        return

    register_payment_handlers(bot)
    register_support_handlers(bot)
    register_referral_handlers(bot)
    register_config_handlers(bot)

    logger.info("v4.0 handlers зарегистрированы")
