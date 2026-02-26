#!/usr/bin/env python3
"""
Hiddify Manager Telegram Bot v2.1
Полнофункциональный бот с UI/UX для приватных пользователей и админки

Новое в v2.1:
- QR код генерация
- Инструкции для платформ
- VLESS URL генерация
- Пробный период
"""

import os
import sys
import sqlite3
import logging
import uuid
import json
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from telebot import TeleBot, types
from dotenv import load_dotenv

# Локальные модули
try:
    from vless_utils import generate_vless_url, validate_vless_url
    from platform_instructions import get_instruction, get_platform_list
    from qr_generator import generate_qr_code
except ImportError:
    print("⚠️  Модули v2.1 не найдены, использую базовую функциональность")
    generate_vless_url = None
    get_instruction = None
    get_platform_list = None
    generate_qr_code = None

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID'))
PANEL_DOMAIN = os.getenv('PANEL_DOMAIN')
HIDDIFY_API_TOKEN = os.getenv('HIDDIFY_API_TOKEN', '')
DB_PATH = os.path.join(os.path.dirname(__file__), '../data/bot.db')

if not BOT_TOKEN:
    print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не найден в .env")
    sys.exit(1)

# Инициализация бота
bot = TeleBot(BOT_TOKEN)

# Создание директории для БД
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), '../logs/bot.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# КОНСТАНТЫ И ВАЛИДАЦИЯ
# ============================================================================

MAX_MESSAGE_LENGTH = 4096
MAX_USERNAME_LENGTH = 32
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def validate_message_length(text: str) -> bool:
    """Проверить длину сообщения"""
    return len(text.encode('utf-8')) <= MAX_MESSAGE_LENGTH


def validate_username(username: str) -> tuple[bool, str]:
    """Валидация username Telegram

    Returns:
        (is_valid, error_message)
    """
    if not username:
        return False, "Username не может быть пустым"

    if not username.startswith('@'):
        return False, "Username должен начинаться с @"

    if len(username) > MAX_USERNAME_LENGTH:
        return False, f"Username слишком длинный (максимум {MAX_USERNAME_LENGTH} символов)"

    # Базовая проверка формата username
    username_part = username[1:]
    if not all(c.isalnum() or c in '_-' for c in username_part):
        return False, "Username содержит недопустимые символы"

    return True, ""


def validate_ip_or_domain(input_str: str) -> tuple[bool, str]:
    """Валидация IP адреса или домена

    Returns:
        (is_valid, error_message)
    """
    if not input_str:
        return False, "Значение не может быть пустым"

    # Базовая проверка длины
    if len(input_str) > 253:
        return False, "Слишком длинное доменное имя"

    # Проверка на IP адрес (IPv4)
    import ipaddress
    try:
        ipaddress.IPv4Address(input_str)
        return True, ""
    except ipaddress.AddressValueError:
        pass

    # Проверка формата домена
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    import re
    if not re.match(domain_pattern, input_str):
        return False, "Некорректный формат домена или IP"

    return True, ""


# ============================================================================
# FSM - МАШИНА СОСТОЯНИЙ
# ============================================================================

# Простая in-memory FSM для отслеживания состояния пользователей
# Ключ: telegram_id, Значение: {'state': str, 'data': dict}
user_states: dict[int, dict] = {}


def set_user_state(telegram_id: int, state: str, data: dict = None):
    """Установить состояние пользователя"""
    user_states[telegram_id] = {
        'state': state,
        'data': data or {}
    }
    logger.debug(f"User {telegram_id} state set to: {state}")


def get_user_state(telegram_id: int) -> dict | None:
    """Получить состояние пользователя"""
    return user_states.get(telegram_id)


def clear_user_state(telegram_id: int):
    """Очистить состояние пользователя"""
    if telegram_id in user_states:
        del user_states[telegram_id]
        logger.debug(f"User {telegram_id} state cleared")


def cancel_operation(telegram_id: int) -> bool:
    """Отменить текущую операцию пользователя

    Returns:
        True если операция была отменена, False если активных операций нет
    """
    state = get_user_state(telegram_id)
    if state:
        state_name = state['state']
        clear_user_state(telegram_id)
        logger.info(f"User {telegram_id} cancelled operation: {state_name}")
        return True
    return False


# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================

def init_db():
    """Инициализация базы данных"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            telegram_username VARCHAR(255),
            telegram_first_name VARCHAR(255),
            user_type VARCHAR(20) DEFAULT 'private',
            invite_code VARCHAR(50) UNIQUE,
            invited_by INTEGER,

            data_limit_bytes BIGINT DEFAULT 104857600000,
            expire_days INTEGER DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,

            used_bytes BIGINT DEFAULT 0,
            last_connection TIMESTAMP,

            is_active BOOLEAN DEFAULT 1,
            is_blocked BOOLEAN DEFAULT 0,

            vless_enabled BOOLEAN DEFAULT 1,
            hysteria2_enabled BOOLEAN DEFAULT 1,
            ss2022_enabled BOOLEAN DEFAULT 1,

            vless_uuid VARCHAR(36),
            hysteria2_password VARCHAR(255),
            ss2022_password VARCHAR(255),

            is_trial BOOLEAN DEFAULT 0,
            trial_expiry TIMESTAMP,
            trial_activated BOOLEAN DEFAULT 0,
            trial_data_limit_gb INTEGER DEFAULT 10
        )
    ''')

    # Таблица подключений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            disconnected_at TIMESTAMP,
            protocol VARCHAR(20),
            location_city VARCHAR(100),
            location_country VARCHAR(100),
            ip_address VARCHAR(45),
            bytes_sent BIGINT DEFAULT 0,
            bytes_received BIGINT DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Таблица инвайтов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(50) UNIQUE NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # Миграция: добавить недостающие колонки для trial функционала
    try:
        # Проверить наличие колонок
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}

        # Добавить недостающие колонки
        if 'is_trial' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN is_trial BOOLEAN DEFAULT 0')
            logger.info("Добавлена колонка is_trial")

        if 'trial_expiry' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN trial_expiry TIMESTAMP')
            logger.info("Добавлена колонка trial_expiry")

        if 'trial_activated' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN trial_activated BOOLEAN DEFAULT 0')
            logger.info("Добавлена колонка trial_activated")

        if 'trial_data_limit_gb' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN trial_data_limit_gb INTEGER DEFAULT 10')
            logger.info("Добавлена колонка trial_data_limit_gb")

    except sqlite3.OperationalError as e:
        logger.warning(f"Миграция не удалась: {e}")

    conn.commit()
    conn.close()

    logger.info("База данных инициализирована")


def get_user(telegram_id):
    """Получить пользователя по telegram_id"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM users WHERE telegram_id = ?
    ''', (telegram_id,))

    user = cursor.fetchone()
    conn.close()

    if user:
        columns = [
            'id', 'telegram_id', 'telegram_username', 'telegram_first_name',
            'user_type', 'invite_code', 'invited_by', 'data_limit_bytes',
            'expire_days', 'created_at', 'expires_at', 'used_bytes',
            'last_connection', 'is_active', 'is_blocked', 'vless_enabled',
            'hysteria2_enabled', 'ss2022_enabled', 'vless_uuid',
            'hysteria2_password', 'ss2022_password',
            'is_trial', 'trial_expiry', 'trial_activated', 'trial_data_limit_gb'
        ]

        return dict(zip(columns, user))

    return None


def create_user(telegram_id, username=None, first_name=None,
                data_limit=104857600000, expire_days=30, invited_by=None):
    """Создать нового пользователя"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Генерация UUID и паролей
    vless_uuid = str(uuid.uuid4())
    hysteria2_password = os.urandom(16).hex()
    ss2022_password = os.urandom(32).hex()
    invite_code = f"INV_{os.urandom(8).hex()}"

    # Расчёт даты истечения
    expires_at = datetime.now() + timedelta(days=expire_days)

    try:
        cursor.execute('''
            INSERT INTO users (
                telegram_id, telegram_username, telegram_first_name,
                data_limit_bytes, expire_days, expires_at, invited_by,
                vless_uuid, hysteria2_password, ss2022_password, invite_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            telegram_id, username, first_name, data_limit, expire_days,
            expires_at, invited_by, vless_uuid, hysteria2_password,
            ss2022_password, invite_code
        ))

        conn.commit()
        user_id = cursor.lastrowid

        logger.info(f"Создан пользователь: {username} (ID: {telegram_id})")

        conn.close()
        return user_id

    except sqlite3.IntegrityError:
        conn.close()
        return None


def is_admin(telegram_id):
    """Проверка прав админа"""

    return telegram_id == ADMIN_ID


# ============================================================================
# UI КОМПОНЕНТЫ (INLINE КЛАВИАТУРЫ)
# ============================================================================

def user_main_keyboard():
    """Главная клавиатура пользователя"""

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = types.KeyboardButton("📱 Мои устройства")
    btn2 = types.KeyboardButton("🔗 Получить ключ")
    btn3 = types.KeyboardButton("📊 Моя подписка")
    btn4 = types.KeyboardButton("💬 Поддержка")
    btn5 = types.KeyboardButton("👥 Пригласить друга")

    markup.add(btn1, btn2, btn3, btn4, btn5)

    return markup


def admin_main_keyboard():
    """Главная клавиатура админа"""

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = types.KeyboardButton("👥 Пользователи")
    btn2 = types.KeyboardButton("➕ Создать юзера")
    btn3 = types.KeyboardButton("📈 Статистика")
    btn4 = types.KeyboardButton("⚙️ Настройки")
    btn5 = types.KeyboardButton("📢 Рассылка")
    btn6 = types.KeyboardButton("🔧 Сервер")
    btn7 = types.KeyboardButton("🚪 Выход")

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)

    return markup


def platform_inline_keyboard():
    """Inline клавиатура выбора платформы"""

    markup = types.InlineKeyboardMarkup(row_width=2)

    btn1 = types.InlineKeyboardButton("📱 iOS", callback_data="platform_ios")
    btn2 = types.InlineKeyboardButton("🤖 Android", callback_data="platform_android")
    btn3 = types.InlineKeyboardButton("💻 Windows", callback_data="platform_windows")
    btn4 = types.InlineKeyboardButton("🍎 macOS", callback_data="platform_macos")
    btn5 = types.InlineKeyboardButton("🐧 Linux", callback_data="platform_linux")
    btn6 = types.InlineKeyboardButton("⚙️ Другое", callback_data="platform_other")

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    return markup


def protocol_inline_keyboard():
    """Inline клавиатура выбора протокола"""

    markup = types.InlineKeyboardMarkup(row_width=1)

    btn1 = types.InlineKeyboardButton(
        "VLESS-Reality ⭐ (Рекомендуется)",
        callback_data="protocol_vless"
    )
    btn2 = types.InlineKeyboardButton(
        "Hysteria2 🚀 (Для мобильных)",
        callback_data="protocol_hysteria2"
    )
    btn3 = types.InlineKeyboardButton(
        "Shadowsocks-2022 🔒 (Резервный)",
        callback_data="protocol_ss2022"
    )

    markup.add(btn1, btn2, btn3)

    return markup


def admin_user_inline_keyboard(user_id):
    """Inline клавиатура управления пользователем"""

    markup = types.InlineKeyboardMarkup(row_width=2)

    btn1 = types.InlineKeyboardButton("🔑 Продлить", callback_data=f"user_extend_{user_id}")
    btn2 = types.InlineKeyboardButton("📦 Лимит", callback_data=f"user_limit_{user_id}")
    btn3 = types.InlineKeyboardButton("🔒 Блок", callback_data=f"user_block_{user_id}")
    btn4 = types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"user_delete_{user_id}")
    btn5 = types.InlineKeyboardButton("📋 Инфо", callback_data=f"user_info_{user_id}")

    markup.add(btn1, btn2, btn3, btn4, btn5)

    return markup


# ============================================================================
# ОБРАБОТЧИКИ КОМАНД - ПОЛЬЗОВАТЕЛЬ
# ============================================================================

@bot.message_handler(commands=['cancel'])
def handle_cancel(message):
    """Обработка команды /cancel - отмена текущей операции"""

    telegram_id = message.chat.id

    if cancel_operation(telegram_id):
        bot.send_message(
            telegram_id,
            "❌ *Операция отменена*\n\n"
            "Вы можете начать заново или выбрать другое действие.",
            parse_mode='Markdown',
            reply_markup=_get_keyboard_for_user(telegram_id)
        )
    else:
        bot.send_message(
            telegram_id,
            "ℹ️ Нет активных операций для отмены.",
            parse_mode='Markdown'
        )


def _get_keyboard_for_user(telegram_id: int):
    """Получить соответствующую клавиатуру для пользователя"""
    if is_admin(telegram_id):
        return admin_main_keyboard()
    return user_main_keyboard()


@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработка команды /start"""

    telegram_id = message.chat.id
    args = message.text.split()

    # Проверка на инвайт-код
    invite_code = None
    if len(args) > 1:
        invite_code = args[1]

    # Проверка существования пользователя
    user = get_user(telegram_id)

    if not user:
        # Новый пользователь
        if invite_code and invite_code.startswith('INV_'):
            # Регистрация по инвайт-коду
            # TODO: Проверить валидность инвайт-кода
            user_id = create_user(
                telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )

            if user_id:
                bot.send_message(
                    telegram_id,
                    "✅ *Добро пожаловать!*\n\n"
                    "Ваш доступ активирован. "
                    "Теперь вы можете пользоваться VPN.",
                    parse_mode='Markdown',
                    reply_markup=user_main_keyboard()
                )
            else:
                bot.send_message(
                    telegram_id,
                    "❌ Ошибка активации. Обратитесь к админу."
                )
        else:
            bot.send_message(
                telegram_id,
                "❌ *Доступ закрыт*\n\n"
                "Для использования бота нужна инвайт-ссылка. "
                "Обратитесь к администратору.",
                parse_mode='Markdown'
            )
        return

    # Существующий пользователь
    if is_admin(telegram_id):
        bot.send_message(
            telegram_id,
            f"👑 *Панель администратора*\n\n"
            f"Выберите действие:",
            parse_mode='Markdown',
            reply_markup=admin_main_keyboard()
        )
    else:
        # Проверка статуса
        if user['is_blocked']:
            bot.send_message(
                telegram_id,
                "⛔ *Ваш доступ заблокирован*\n\n"
                "Обратитесь к администратору для уточнения деталей.",
                parse_mode='Markdown'
            )
            return

        # Проверка срока действия
        if user['expires_at']:
            expire_date = datetime.fromisoformat(user['expires_at'])
            if expire_date < datetime.now():
                bot.send_message(
                    telegram_id,
                    "⚠️ *Ваша подписка истекла*\n\n"
                    "Обратитесь к администратору для продления.",
                    parse_mode='Markdown'
                )
                return

        bot.send_message(
            telegram_id,
            f"🛡️ *{bot.get_me().first_name}*\n\n"
            f"Добро пожаловать, {user['telegram_first_name']}!\n"
            f"Статус: ✅ Активен",
            parse_mode='Markdown',
            reply_markup=user_main_keyboard()
        )

    logger.info(f"Пользователь {telegram_id} запустил /start")


@bot.message_handler(func=lambda message: message.text == "📱 Мои устройства")
def handle_my_devices(message):
    """Обработка кнопки 'Мои устройства'"""

    telegram_id = message.chat.id
    user = get_user(telegram_id)

    if not user:
        return

    # TODO: Запрос к API Hiddify для получения активных подключений
    # Временный заглушка
    response = (
        "📱 *Мои устройства*\n\n"
        "Активные подключения:\n\n"
        "┌────────────────────────────┐\n"
        "│ 📱 iPhone 15 Pro            │\n"
        "│ Москва, Россия              │\n"
        "│ Подключен: 2 мин назад     │\n"
        "│ Протокол: VLESS-Reality    │\n"
        "│ Трафик: 1.2 GB / 100 GB    │\n"
        "└────────────────────────────┘\n\n"
        "*(функционал в разработке)*"
    )

    bot.send_message(telegram_id, response, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "🔗 Получить ключ")
def handle_get_key(message):
    """Обработка кнопки 'Получить ключ'"""

    telegram_id = message.chat.id
    user = get_user(telegram_id)

    if not user:
        return

    bot.send_message(
        telegram_id,
        "🔗 *Получить конфигурацию*\n\n"
        "Выберите протокол:",
        parse_mode='Markdown',
        reply_markup=protocol_inline_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "📊 Моя подписка")
def handle_my_subscription(message):
    """Обработка кнопки 'Моя подписка' с поддержкой trial"""

    telegram_id = message.chat.id
    user = get_user(telegram_id)

    if not user:
        return

    # Проверка на пробный период
    is_trial = user.get('is_trial', False)
    trial_expiry = user.get('trial_expiry')

    # Если trial истёк
    if is_trial and trial_expiry:
        trial_end = datetime.fromisoformat(trial_expiry)
        if datetime.now() > trial_end:
            # Trial истёк, показать предложение продления
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("💳 Купить подписку", callback_data="buy_subscription")
            )

            bot.send_message(
                telegram_id,
                "📊 *Пробный период истёк*\n\n"
                "Ваш пробный период завершён. Оформите подписку для продолжения использования.",
                parse_mode='Markdown',
                reply_markup=markup
            )
            return

    # Расчёт процента использования трафика
    data_limit = user['data_limit_bytes']
    used_bytes = user.get('used_bytes', 0)
    used_percent = (used_bytes / data_limit) * 100 if data_limit > 0 else 0
    used_gb = used_bytes / (1024**3)
    limit_gb = data_limit / (1024**3)

    # Формирование строки даты истечения
    expire_str = "Бессрочно"
    days_left = "∞"

    if is_trial and trial_expiry:
        trial_end = datetime.fromisoformat(trial_expiry)
        days_left = max(0, (trial_end - datetime.now()).days)
        expire_str = trial_end.strftime("%d.%m.%Y")
    elif user['expires_at']:
        expire_date = datetime.fromisoformat(user['expires_at'])
        days_left = (expire_date - datetime.now()).days
        expire_str = expire_date.strftime("%d.%m.%Y")

    # Формирование сообщения
    subscription_type = "Пробный период" if is_trial else "Приватный"

    response = (
        f"📊 *Моя подписка*\n\n"
        f"Статус: ✅ Активен\n\n"
        f"Тип: {subscription_type}\n"
        f"Истекает: {expire_str} (осталось {days_left} дней)\n\n"
        f"Лимит трафика:\n"
        f"{used_percent:.1f}% - {used_gb:.1f} GB / {limit_gb:.0f} GB\n\n"
        f"Протоколы:\n"
        f"{'✅' if user['vless_enabled'] else '❌'} VLESS-Reality\n"
        f"{'✅' if user['hysteria2_enabled'] else '❌'} Hysteria2\n"
        f"{'✅' if user['ss2022_enabled'] else '❌'} Shadowsocks-2022"
    )

    # Если не trial и не был активирован, показать кнопку trial
    if not is_trial and not user.get('trial_activated'):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎁 Активировать пробный период", callback_data="activate_trial")
        )

        bot.send_message(
            telegram_id,
            response + "\n\n💡 *Хотите попробовать бесплатно?*",
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        bot.send_message(telegram_id, response, parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'activate_trial')
def handle_activate_trial(call):
    """
    Активация пробного периода (7 дней, 10 GB)
    """

    telegram_id = call.message.chat.id
    user = get_user(telegram_id)

    if not user:
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return

    # Проверка: trial уже активирован?
    if user.get('trial_activated') or user.get('is_trial'):
        bot.answer_callback_query(call.id, "Пробный период уже активирован", show_alert=True)
        return

    # Проверка: есть ли уже активная подписка?
    if user.get('expires_at'):
        expire_date = datetime.fromisoformat(user['expires_at'])
        if expire_date > datetime.now():
            bot.answer_callback_query(call.id, "У вас уже есть активная подписка", show_alert=True)
            return

    # Активация trial
    trial_end = datetime.now() + timedelta(days=7)
    trial_limit_gb = user.get('trial_data_limit_gb', 10)
    trial_limit_bytes = trial_limit_gb * (1024**3)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users
        SET is_trial = TRUE,
            trial_expiry = ?,
            trial_activated = TRUE,
            data_limit_bytes = ?,
            expires_at = ?
        WHERE telegram_id = ?
    ''', (trial_end.isoformat(), trial_limit_bytes, trial_end.isoformat(), telegram_id))

    conn.commit()
    conn.close()

    logger.info(f"Активирован trial для пользователя {telegram_id}")

    bot.send_message(
        telegram_id,
        "🎉 *Пробный период активирован!*\n\n"
        f"📅 Длительность: 7 дней\n"
        f"📊 Лимит трафика: {trial_limit_gb} GB\n\n"
        f"⏰ Истекает: {trial_end.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Нажмите 'Получить ключ' для подключения!",
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, "Пробный период активирован")


@bot.message_handler(func=lambda message: message.text == "💬 Поддержка")
def handle_support(message):
    """Обработка кнопки 'Поддержка' с инструкциями по платформам"""

    telegram_id = message.chat.id

    markup = types.InlineKeyboardMarkup(row_width=1)

    # Кнопка выбора платформы (v2.1)
    btn_platform = types.InlineKeyboardButton(
        "📱 Инструкция для вашего устройства",
        callback_data="show_platforms"
    )
    btn1 = types.InlineKeyboardButton(
        "❓ Медленная скорость? 🐌",
        callback_data="support_speed"
    )
    btn2 = types.InlineKeyboardButton(
        "❓ Не работает? 🔧",
        callback_data="support_troubleshoot"
    )

    markup.add(btn_platform, btn1, btn2)

    bot.send_message(
        telegram_id,
        "💬 *Поддержка*\n\n"
        "Выберите тему:",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == "👥 Пригласить друга")
def handle_invite(message):
    """Обработка кнопки 'Пригласить друга'"""

    telegram_id = message.chat.id
    user = get_user(telegram_id)

    if not user:
        return

    # TODO: Реализовать систему инвайтов и подсчёт приглашённых
    invite_link = f"https://t.me/{bot.get_me().username}?start={user['invite_code']}"

    response = (
        f"👥 *Пригласить друга*\n\n"
        f"Поделитесь ссылкой для регистрации:\n\n"
        f"`{invite_link}`\n\n"
        f"После перехода по ссылке:\n"
        f"• Друг автоматически получит доступ\n"
        f"• Вам не нужно ничего оплачивать\n"
        f"• Доступ бессрочный"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)

    btn1 = types.InlineKeyboardButton("📤 Скопировать", callback_data="invite_copy")
    btn2 = types.InlineKeyboardButton("📨 Отправить", url=f"https://t.me/share/url?url={invite_link}")

    markup.add(btn1, btn2)

    bot.send_message(telegram_id, response, parse_mode='Markdown', reply_markup=markup)


# ============================================================================
# ОБРАБОТЧИКИ КОМАНД - АДМИН
# ============================================================================

@bot.message_handler(func=lambda message: message.text == "👥 Пользователи")
def handle_admin_users(message):
    """Обработка кнопки 'Пользователи' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    # TODO: Получить список пользователей из БД
    bot.send_message(
        telegram_id,
        "👥 *Пользователи*\n\n"
        "(функционал в разработке)\n\n"
        "Всего: 0\n"
        "Активных: 0",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == "➕ Создать юзера")
def handle_admin_create_user(message):
    """Обработка кнопки 'Создать юзера' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    # Установить состояние
    set_user_state(telegram_id, 'creating_user_step_username')

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_operation"))

    bot.send_message(
        telegram_id,
        "➕ *Создать пользователя*\n\n"
        "Шаг 1 из 2: Введите username Telegram\n\n"
        "Пример: @username\n\n"
        "Или отправьте forward сообщения от пользователя",
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.register_next_step_handler(message, process_create_user_username)


def process_create_user_username(message):
    """Обработка ввода username при создании пользователя"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        clear_user_state(telegram_id)
        return

    # Проверка отмены
    state = get_user_state(telegram_id)
    if not state or state.get('state') != 'creating_user_step_username':
        bot.send_message(
            telegram_id,
            "⚠️ Операция была прервана. Нажмите 'Создать юзера' для начала.",
            parse_mode='Markdown',
            reply_markup=admin_main_keyboard()
        )
        clear_user_state(telegram_id)
        return

    username = message.text.strip()

    # Валидация с использованием новой функции
    is_valid, error_msg = validate_username(username)
    if not is_valid:
        # Добавить кнопку отмены
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_operation"))

        bot.send_message(
            telegram_id,
            f"❌ {error_msg}\n\n"
            f"Попробуйте ещё раз или нажмите 'Отмена':",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.register_next_step_handler(message, process_create_user_username)
        return

    # Сохранить username в состояние
    state['data']['username'] = username
    set_user_state(telegram_id, 'creating_user_step_confirm', state['data'])

    # Показать подтверждение с кнопками
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_create_user"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_operation")
    )

    bot.send_message(
        telegram_id,
        f"➕ *Подтверждение создания*\n\n"
        f"Username: {username}\n\n"
        f"Лимит трафика: 100 GB\n"
        f"Срок действия: 30 дней\n\n"
        f"Создать пользователя?",
        parse_mode='Markdown',
        reply_markup=markup
    )

    # Не регистрируем next step handler - ждём callback


@bot.message_handler(func=lambda message: message.text == "📈 Статистика")
def handle_admin_stats(message):
    """Обработка кнопки 'Статистика' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    # TODO: Получить реальную статистику
    bot.send_message(
        telegram_id,
        "📈 *Статистика системы*\n\n"
        "Период: Сегодня\n\n"
        "👥 Пользователи:\n"
        "Всего: 0\n"
        "Активных: 0\n\n"
        "📊 Трафик:\n"
        "Сегодня: 0 GB\n\n"
        "(функционал в разработке)",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == "⚙️ Настройки")
def handle_admin_settings(message):
    """Обработка кнопки 'Настройки' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    bot.send_message(
        telegram_id,
        "⚙️ *Настройки сервера*\n\n"
        "(функционал в разработке)\n\n"
        "Домен панели: panel.yourvpn.ru\n"
        "Автообновление: ✅",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == "📢 Рассылка")
def handle_admin_broadcast(message):
    """Обработка кнопки 'Рассылка' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    bot.send_message(
        telegram_id,
        "📢 *Рассылка уведомлений*\n\n"
        "(функционал в разработке)",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == "🔧 Сервер")
def handle_admin_server(message):
    """Обработка кнопки 'Сервер' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    bot.send_message(
        telegram_id,
        "🔧 *Управление сервером*\n\n"
        "(функционал в разработке)\n\n"
        "Hiddify Manager: ✅ Active\n"
        "Xray: ✅ Active\n"
        "Telegram Bot: ✅ Active",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == "🚪 Выход")
def handle_admin_exit(message):
    """Обработка кнопки 'Выход' из админки"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    bot.send_message(
        telegram_id,
        "👋 Выход из админки...",
        reply_markup=user_main_keyboard()
    )


# ============================================================================
# CALLBACK HANDLERS (INLINE BUTTONS)
# ============================================================================

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_operation')
def handle_cancel_callback(call):
    """Обработка кнопки отмены операции"""

    telegram_id = call.message.chat.id

    if cancel_operation(telegram_id):
        bot.answer_callback_query(call.id, "Операция отменена")
        bot.send_message(
            telegram_id,
            "❌ *Операция отменена*",
            parse_mode='Markdown',
            reply_markup=admin_main_keyboard() if is_admin(telegram_id) else user_main_keyboard()
        )
    else:
        bot.answer_callback_query(call.id, "Нет активных операций", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_create_user')
def handle_confirm_create_user(call):
    """Подтверждение создания пользователя"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return

    state = get_user_state(telegram_id)
    if not state or state.get('state') != 'creating_user_step_confirm':
        bot.answer_callback_query(call.id, "Операция устарела", show_alert=True)
        clear_user_state(telegram_id)
        return

    username = state['data'].get('username')

    # TODO: Реальное создание пользователя в БД
    # Сейчас это заглушка - нужно вызвать create_user() с параметрами

    clear_user_state(telegram_id)

    bot.answer_callback_query(call.id, "Пользователь создан")
    bot.send_message(
        telegram_id,
        f"✅ *Пользователь {username} создан!*\n\n"
        f"(функционал в разработке)\n\n"
        f"Лимит: 100 GB\n"
        f"Срок: 30 дней",
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )

    logger.info(f"Admin {telegram_id} created user: {username}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('protocol_'))
def handle_protocol_selection(call):
    """
    Обработка выбора протокола с QR кодом и инструкциями
    """

    telegram_id = call.message.chat.id
    protocol = call.data.split('_')[1]

    user = get_user(telegram_id)

    if not user:
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return

    # Генерация конфига для выбранного протокола
    if protocol == 'vless':
        # Используем vless_utils если доступен
        if generate_vless_url:
            config_link = generate_vless_url(
                user_uuid=user['vless_uuid'],
                name=f"SKRT-VPN-{user.get('telegram_first_name', 'User')}"
            )
        else:
            # Fallback на старый метод
            config_link = f"vless://{user['vless_uuid']}@{os.getenv('VPS_IP')}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.apple.com&fp=chrome&pbk={os.getenv('REALITY_PUBLIC_KEY')}&type=tcp&header=none#SKRT-VPN"

        config_name = "VLESS-Reality"

    elif protocol == 'hysteria2':
        config_link = f"hysteria2://{user['hysteria2_password']}@{os.getenv('VPS_IP')}:443/?sni={os.getenv('REALITY_SNI', 'www.apple.com')}&alpn=h3#SKRT-Hysteria2"
        config_name = "Hysteria2"

    else:  # shadowsocks
        config_link = f"ss2022://{user['ss2022_password']}@{os.getenv('VPS_IP')}:8388/?security=2022-blake3-aes-256-gcm#SKRT-SS2022"
        config_name = "Shadowsocks-2022"

    # Генерация QR кода если доступен
    if generate_qr_code:
        try:
            qr_buffer = generate_qr_code(config_link, box_size=8, border=4)

            bot.send_photo(
                telegram_id,
                photo=qr_buffer.getvalue(),
                caption=f"📋 *Конфигурация: {config_name}*\n\n"
                        f"🔗 *Ссылка:*\n`{config_link}`\n\n"
                        f"📱 *Как подключиться:*\n"
                        f"1. Отсканируйте QR код или скопируйте ссылку\n"
                        f"2. Откройте клиент (Nekobox/V2Ray)\n"
                        f"3. Импортируйте конфиг\n"
                        f"4. Подключитесь\n\n"
                        f"❓ *Нужна инструкция?* Нажмите /help",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Ошибка генерации QR: {e}")
            # Fallback без QR
            bot.send_message(
                telegram_id,
                f"📋 *Конфигурация: {config_name}*\n\n"
                f"<code>{config_link}</code>\n\n"
                f"📱 *Как подключиться:*\n"
                f"1. Скопируйте ссылку (длинное нажатие)\n"
                f"2. Откройте клиент (Nekobox/V2Ray)\n"
                f"3. Импортируйте из буфера обмена\n"
                f"4. Подключитесь",
                parse_mode='HTML'
            )
    else:
        # Без QR кода (старый метод)
        bot.send_message(
            telegram_id,
            f"📋 *Конфигурация: {config_name}*\n\n"
            f"<code>{config_link}</code>\n\n"
            f"📱 *Как подключиться:*\n"
            f"1. Скопируйте ссылку (длинное нажатие)\n"
            f"2. Откройте клиент (Nekobox/V2Ray)\n"
            f"3. Импортируйте из буфера обмена\n"
            f"4. Подключитесь",
            parse_mode='HTML'
        )

    bot.answer_callback_query(call.id, "Конфигурация отправлена")


@bot.callback_query_handler(func=lambda call: call.data.startswith('platform_'))
def handle_platform_selection(call):
    """
    Обработка выбора платформы для инструкций
    """

    telegram_id = call.message.chat.id
    platform = call.data.split('_')[1]  # ios, android, windows, mac, linux

    if not get_instruction:
        bot.answer_callback_query(call.id, "Инструкции недоступны")
        return

    instruction = get_instruction(platform)

    message_text = (
        f"{instruction['icon']} *{instruction['name']}*\n\n"
        f"{instruction['steps']}\n\n"
        f"📥 *Скачать клиент:*\n{instruction['download']}"
    )

    # Создаем кнопку с инструкцией по устранению проблем
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔧 Решение проблем", callback_data=f"troubleshoot_{platform}"),
        types.InlineKeyboardButton("↩️ Назад", callback_data="help")
    )

    bot.send_message(
        telegram_id,
        message_text,
        parse_mode='Markdown',
        reply_markup=markup,
        disable_web_page_preview=True
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('troubleshoot_'))
def handle_troubleshoot(call):
    """
    Показать инструкцию по устранению проблем
    """

    telegram_id = call.message.chat.id
    platform = call.data.split('_')[1]  # ios, android, windows, mac, linux

    if not get_instruction:
        bot.answer_callback_query(call.id, "Инструкции недоступны")
        return

    instruction = get_instruction(platform)

    bot.send_message(
        telegram_id,
        instruction['troubleshoot'],
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'invite_copy')
def handle_invite_copy(call):
    """Обработка копирования инвайт-ссылки"""

    telegram_id = call.message.chat.id
    user = get_user(telegram_id)

    if not user:
        bot.answer_callback_query(call.id, "Ошибка")
        return

    invite_link = f"https://t.me/{bot.get_me().username}?start={user['invite_code']}"

    bot.answer_callback_query(call.id, "Ссылка скопирована", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == 'show_platforms')
def handle_show_platforms(call):
    """Показать выбор платформы для инструкций"""

    telegram_id = call.message.chat.id

    bot.send_message(
        telegram_id,
        "📱 *Выберите вашу платформу*\n\n"
        "Мы покажем пошаговую инструкцию для подключения:",
        parse_mode='Markdown',
        reply_markup=platform_inline_keyboard()
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('support_'))
def handle_support_callbacks(call):
    """Обработка кнопок поддержки"""

    action = call.data.split('_')[1]

    responses = {
        'speed': "🐌 *Медленная скорость?*\n\nПопробуйте:\n1. Сменить протокол на Hysteria2\n2. Проверить свой интернет\n3. Подключиться к другому серверу",
        'troubleshoot': "🔧 *Не работает?*\n\nПроверьте:\n1. Срок действия подписки\n2. Лимит трафика\n3. Правильность импорта конфига\n\nЕсли ничего не помогает — напишите админу."
    }

    bot.send_message(
        call.message.chat.id,
        responses.get(action, "Раздел в разработке"),
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id)


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция"""

    logger.info("Бот запускается...")
    logger.info(f"ADMIN_ID: {ADMIN_ID}")
    logger.info(f"BOT_USERNAME: @{bot.get_me().username}")

    # Инициализация БД
    init_db()

    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
