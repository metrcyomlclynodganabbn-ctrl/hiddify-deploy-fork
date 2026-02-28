#!/usr/bin/env python3
"""
Hiddify Manager Telegram Bot v4.0.0
Полнофункциональный бот с UI/UX для приватных пользователей и админки

Новое в v4.0.0:
- PostgreSQL вместо SQLite
- Redis кэширование
- Stripe платежи
- Support tickets
- Referral программа
- Config Builder (Standard/Enhanced)
- Prometheus + Grafana мониторинг

Новое в v3.0.0:
- Интеграция с Hiddify Manager API
- Реальная админка (пользователи, статистика, создание юзеров)
- Система инвайтов с валидацией
- Отображение активных устройств
- Graceful degradation при недоступности API

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
    from hiddify_api import (
        HiddifyAPI, HiddifyAPIError,
        validate_invite_code, use_invite_code, create_invite_code
    )
    # v3.1: Система ролей
    from roles import (
        Role, get_user_role, is_admin as check_is_admin,
        is_manager, can_invite_users, set_user_role,
        get_role_display_name
    )
    # v4.0: Новые модули (дополнительно)
    try:
        from scripts.v4_handlers import register_all_v4_handlers, init_v4_modules
        V4_AVAILABLE = True
    except ImportError as e:
        V4_AVAILABLE = False
        logger.info(f"v4.0 модули не доступны: {e}")
except ImportError:
    print("⚠️  Модули v2.1 не найдены, использую базовую функциональность")
    generate_vless_url = None
    get_instruction = None
    get_platform_list = None
    generate_qr_code = None
    HiddifyAPI = None
    validate_invite_code = None
    use_invite_code = None
    create_invite_code = None
    # Fallback для ролей
    Role = None
    get_user_role = None
    check_is_admin = None
    is_manager = None
    can_invite_users = None
    set_user_role = None
    get_role_display_name = None
    V4_AVAILABLE = False
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


def escape_markdown(text: str) -> str:
    """Экранировать спецсимволы Markdown для Telegram

    Args:
        text: Исходный текст

    Returns:
        Текст с экранированными спецсимволами
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

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
    """Инициализация базы данных с WAL mode для конкурентного доступа"""

    conn = sqlite3.connect(DB_PATH)

    # Включить WAL mode для параллельного чтения/записи
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('PRAGMA foreign_keys=ON')

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
            trial_data_limit_gb INTEGER DEFAULT 10,

            role VARCHAR(20) DEFAULT 'user'
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
    """
    Проверка прав админа

    v3.1: Использует систему ролей если доступна, иначе fallback на ADMIN_ID
    """
    if check_is_admin is not None:
        # Используем новую систему ролей
        return check_is_admin(telegram_id)
    else:
        # Fallback для обратной совместимости
        return telegram_id == ADMIN_ID


def get_users_list(limit: int = 50, offset: int = 0) -> list[dict]:
    """Получить список пользователей из БД

    Args:
        limit: Максимальное количество пользователей
        offset: Смещение для пагинации

    Returns:
        List[dict] с данными пользователей
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM users
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    columns = [
        'id', 'telegram_id', 'telegram_username', 'telegram_first_name',
        'user_type', 'invite_code', 'invited_by', 'data_limit_bytes',
        'expire_days', 'created_at', 'expires_at', 'used_bytes',
        'last_connection', 'is_active', 'is_blocked', 'vless_enabled',
        'hysteria2_enabled', 'ss2022_enabled', 'vless_uuid',
        'hysteria2_password', 'ss2022_password',
        'is_trial', 'trial_expiry', 'trial_activated', 'trial_data_limit_gb'
    ]

    return [dict(zip(columns, row)) for row in rows]


def get_users_stats() -> dict:
    """Получить статистику по пользователям

    Returns:
        Dict с данными:
            - total_users: Всего пользователей
            - active_users: Активных пользователей
            - trial_users: Пользователей с trial
            - blocked_users: Заблокированных пользователей
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
    active_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_trial = 1')
    trial_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
    blocked_users = cursor.fetchone()[0]

    conn.close()

    return {
        'total_users': total_users,
        'active_users': active_users,
        'trial_users': trial_users,
        'blocked_users': blocked_users
    }


# ============================================================================
# UI КОМПОНЕНТЫ (INLINE КЛАВИАТУРЫ)
# ============================================================================

def user_main_keyboard(telegram_id=None):
    """
    Главная клавиатура пользователя (с ограничением по ролям)

    Args:
        telegram_id: Telegram ID пользователя для проверки прав.
                     Если None, кнопка "Пригласить друга" не показывается.
    """

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = types.KeyboardButton("📱 Мои устройства")
    btn2 = types.KeyboardButton("🔗 Получить ключ")
    btn3 = types.KeyboardButton("📊 Моя подписка")
    btn4 = types.KeyboardButton("💬 Поддержка")

    # Добавляем кнопку "Пригласить друга" только для manager/admin
    show_invite = False
    if telegram_id and can_invite_users:
        try:
            show_invite = can_invite_users(telegram_id)
        except Exception:
            # Graceful degradation - не показываем кнопку при ошибке
            show_invite = False

    markup.add(btn1, btn2, btn3, btn4)

    if show_invite:
        btn5 = types.KeyboardButton("👥 Пригласить друга")
        markup.add(btn5)

    # v4.0: Новые кнопки
    if V4_AVAILABLE:
        btn5_v4 = types.KeyboardButton("💳 Купить подписку")
        btn6_v4 = types.KeyboardButton("👥 Рефералы")
        markup.add(btn5_v4, btn6_v4)

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
    return user_main_keyboard(telegram_id)


@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработка команды /start"""

    telegram_id = message.chat.id
    args = message.text.split()

    # Проверка на инвайт-код
    invite_code = None
    ref_referrer_id = None  # v4.0: Реферальный код

    if len(args) > 1:
        start_param = args[1]
        if start_param.startswith('INV_'):
            # Инвайт-код (v3.x)
            invite_code = start_param
        elif V4_AVAILABLE and start_param.startswith('ref_'):
            # Реферальный код (v4.0)
            try:
                ref_referrer_id = int(start_param.split('_')[1])
                logger.info(f"Пользователь {telegram_id} пришёл по реферальной ссылке от {ref_referrer_id}")
            except (ValueError, IndexError):
                pass

    # Проверка существования пользователя
    user = get_user(telegram_id)

    # Если пользователь не найден, проверяем - не был ли он создан админом (telegram_id = 0)?
    if not user:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = 0 ORDER BY created_at DESC LIMIT 1')
        pending_user = cursor.fetchone()
        conn.close()

        if pending_user:
            # Пользователь был создан админом - активируем его
            columns = [
                'id', 'telegram_id', 'telegram_username', 'telegram_first_name',
                'user_type', 'invite_code', 'invited_by', 'data_limit_bytes',
                'expire_days', 'created_at', 'expires_at', 'used_bytes',
                'last_connection', 'is_active', 'is_blocked', 'vless_enabled',
                'hysteria2_enabled', 'ss2022_enabled', 'vless_uuid',
                'hysteria2_password', 'ss2022_password',
                'is_trial', 'trial_expiry', 'trial_activated', 'trial_data_limit_gb'
            ]
            user = dict(zip(columns, pending_user))

            # Обновляем telegram_id на реальный
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET telegram_id = ?, telegram_username = ?, telegram_first_name = ?
                WHERE id = ?
            ''', (telegram_id, message.from_user.username, message.from_user.first_name, user['id']))
            conn.commit()
            conn.close()

            logger.info(f"Пользователь {user['telegram_username']} активирован: telegram_id={telegram_id}")

            # Отправляем приветствие
            bot.send_message(
                telegram_id,
                f"✅ *Добро пожаловать, {user['telegram_first_name']}!*\n\n"
                f"Ваш доступ уже был активирован. "
                f"Нажмите 'Получить ключ' для подключения.",
                parse_mode='Markdown',
                reply_markup=user_main_keyboard(telegram_id)
            )
            return

    # Совсем новый пользователь (нет в БД и нет pending записей)
    if not user:
        # Новый пользователь - нужна инвайт-ссылка
        if invite_code and invite_code.startswith('INV_'):
            # Проверка валидности инвайт-кода
            invite_valid = False
            if validate_invite_code:
                invite_data = validate_invite_code(DB_PATH, invite_code)
                invite_valid = invite_data is not None

            if invite_valid:
                # Регистрация по инвайт-коду
                user_id = create_user(
                    telegram_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name
                )

                if user_id:
                    # Увеличить счётчик использований инвайта
                    if use_invite_code:
                        use_invite_code(DB_PATH, invite_code)

                    # v4.0: Создать реферальную запись если пришёл по реф ссылке
                    if V4_AVAILABLE and ref_referrer_id:
                        try:
                            from referral.referral_manager import referral_manager
                            import asyncio
                            asyncio.run(referral_manager.create_referral(
                                referrer_id=ref_referrer_id,
                                referred_id=telegram_id
                            ))
                            logger.info(f"Реферальная запись создана: {ref_referrer_id} -> {telegram_id}")
                        except Exception as e:
                            logger.warning(f"Не удалось создать реферальную запись: {e}")

                    bot.send_message(
                        telegram_id,
                        "✅ *Добро пожаловать!*\n\n"
                        "Ваш доступ активирован. "
                        "Теперь вы можете пользоваться VPN.",
                        parse_mode='Markdown',
                        reply_markup=user_main_keyboard(telegram_id)
                    )
                else:
                    bot.send_message(
                        telegram_id,
                        "❌ Ошибка активации. Обратитесь к админу."
                    )
            else:
                bot.send_message(
                    telegram_id,
                    "❌ *Неверный инвайт-код*\n\n"
                    "Ссылка недействительна или истекла. "
                    "Обратитесь к администратору.",
                    parse_mode='Markdown'
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
            reply_markup=user_main_keyboard(telegram_id)
        )

    logger.info(f"Пользователь {telegram_id} запустил /start")


@bot.message_handler(func=lambda message: message.text == "📱 Мои устройства")
def handle_my_devices(message):
    """Обработка кнопки 'Мои устройства'"""

    telegram_id = message.chat.id
    user = get_user(telegram_id)

    if not user:
        return

    # Попробовать получить активные подключения через Hiddify API
    connections = []
    if HiddifyAPI and user.get('vless_uuid'):
        try:
            api = HiddifyAPI()
            connections = api.get_user_connections(user['vless_uuid'])
        except Exception as e:
            logger.warning(f"Не удалось получить подключения: {e}")

    if connections:
        response = "📱 *Мои устройства*\n\nАктивные подключения:\n\n"
        for conn in connections[:10]:  # Максимум 10 подключений
            device = conn.get('device', 'Неизвестное устройство')
            location = conn.get('location', 'N/A')
            connected_at = conn.get('connected_at', 'N/A')
            protocol = conn.get('protocol', 'N/A')

            response += (
                f"┌────────────────────────────┐\n"
                f"│ 📱 {device:<24} │\n"
                f"│ 📍 {location:<24} │\n"
                f"│ ⏰ {connected_at:<23} │\n"
                f"│ 🔐 {protocol:<23} │\n"
                f"└────────────────────────────┘\n\n"
            )
    else:
        # Заглушка если API недоступен
        response = (
            "📱 *Мои устройства*\n\n"
            "Активные подключения:\n\n"
            "Нет данных о подключениях\n\n"
        )
        if not HiddifyAPI:
            response += "*(API интеграция в процессе настройки)*"

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

    # Проверка прав на приглашение (v3.1.1)
    if can_invite_users and not can_invite_users(telegram_id):
        bot.send_message(
            telegram_id,
            "❌ *Доступ запрещён*\n\n"
            "Функция приглашения доступна только для менеджеров и администраторов.",
            parse_mode='Markdown'
        )
        return

    # Получить количество приглашённых
    invited_count = 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM users WHERE invited_by = ?', (telegram_id,))
        invited_count = cursor.fetchone()[0]
    except Exception:
        pass
    finally:
        conn.close()

    invite_link = f"https://t.me/{bot.get_me().username}?start={user['invite_code']}"

    response = (
        f"👥 *Пригласить друга*\n\n"
        f"Поделитесь ссылкой для регистрации:\n\n"
        f"`{invite_link}`\n\n"
        f"Вы пригласили: {invited_count} человек\n\n"
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

    # Получить список пользователей
    users = get_users_list(limit=50)

    if not users:
        bot.send_message(
            telegram_id,
            "👥 *Пользователи*\n\n"
            "Пользователей нет",
            parse_mode='Markdown'
        )
        return

    # Формировать сообщение
    response = "👥 *Пользователи* (последние 50)\n\n"

    for user in users[:20]:  # Показываем первые 20
        username = user.get('telegram_username') or user.get('telegram_first_name', 'Без имени')
        status = "✅" if user.get('is_active') else "❌"
        trial = " 🎁" if user.get('is_trial') else ""
        created = user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'

        response += f"{status} @{username}{trial}\n"
        response += f"   ID: {user['telegram_id']} | {created}\n\n"

    response += f"Всего: {len(users)}"

    # Проверка длины сообщения
    if len(response.encode('utf-8')) > MAX_MESSAGE_LENGTH:
        response = "👥 *Пользователи*\n\n" + f"Всего: {len(users)}\n\nСлишком много для отображения"

    bot.send_message(telegram_id, response, parse_mode='Markdown')


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

    # Получить статистику из SQLite
    stats = get_users_stats()

    # Попробовать получить статистику из Hiddify API
    api_stats = {}
    if HiddifyAPI:
        try:
            api = HiddifyAPI()
            api_stats = api.get_stats()
        except Exception as e:
            logger.warning(f"Не удалось получить статистику из API: {e}")

    # Формирование сообщения
    response = (
        "📈 *Статистика системы*\n\n"
        f"👥 Пользователи:\n"
        f"Всего: {stats['total_users']}\n"
        f"Активных: {stats['active_users']}\n"
        f"Trial: {stats['trial_users']}\n"
        f"Заблокировано: {stats['blocked_users']}\n\n"
    )

    if api_stats:
        today_traffic = api_stats.get('today_traffic', 'N/A')
        month_traffic = api_stats.get('month_traffic', 'N/A')
        response += (
            f"📊 Трафик:\n"
            f"Сегодня: {today_traffic}\n"
            f"Месяц: {month_traffic}\n\n"
        )

    response += f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    bot.send_message(telegram_id, response, parse_mode='Markdown')


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
        reply_markup=user_main_keyboard(telegram_id)
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
            reply_markup=admin_main_keyboard() if is_admin(telegram_id) else user_main_keyboard(telegram_id)
        )
    else:
        bot.answer_callback_query(call.id, "Нет активных операций", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_create_user')
def handle_confirm_create_user(call):
    """Подтверждение создания пользователя - РЕАЛЬНОЕ создание"""

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
    data_limit = 100  # GB
    expire_days = 30

    try:
        # 1. Проверить, существует ли пользователь с таким username
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE telegram_username = ?', (username,))
        existing = cursor.fetchone()
        conn.close()

        if existing:
            clear_user_state(telegram_id)
            bot.answer_callback_query(call.id, "Пользователь уже существует", show_alert=True)
            bot.send_message(
                telegram_id,
                f"⚠️ Пользователь {escape_markdown(username)} уже существует в системе.",
                parse_mode='Markdown',
                reply_markup=admin_main_keyboard()
            )
            return

        # 2. Создать запись в SQLite
        # Используем telegram_id = 0 как временное значение (пользователь ещё не в боте)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Генерация UUID и паролей
        vless_uuid = str(uuid.uuid4())
        hysteria2_password = os.urandom(16).hex()
        ss2022_password = os.urandom(32).hex()
        invite_code = f"INV_{os.urandom(8).hex()}"
        expires_at = datetime.now() + timedelta(days=expire_days)

        cursor.execute('''
            INSERT INTO users (
                telegram_id, telegram_username, telegram_first_name,
                data_limit_bytes, expire_days, expires_at,
                vless_uuid, hysteria2_password, ss2022_password, invite_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            0,  # Временное значение - пользователь ещё не в боте
            username,
            username.split('@')[-1],  # Имя без @
            data_limit * 1024**3,
            expire_days,
            expires_at.isoformat(),
            vless_uuid,
            hysteria2_password,
            ss2022_password,
            invite_code
        ))

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # 3. Попытка создать через Hiddify API (если доступен)
        api_success = False
        if HiddifyAPI:
            try:
                api = HiddifyAPI()
                api.create_user(
                    username=username,
                    data_limit_gb=data_limit,
                    expire_days=expire_days
                )
                api_success = True
                logger.info(f"Пользователь {username} создан через Hiddify API")
            except HiddifyAPIError as e:
                logger.warning(f"Не удалось создать пользователя через API: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")

        # 4. Отправить результат
        clear_user_state(telegram_id)
        bot.answer_callback_query(call.id, "Пользователь создан")

        result_message = (
            f"✅ *Пользователь {escape_markdown(username)} создан!*\n\n"
            f"📦 Лимит: {data_limit} GB\n"
            f"📅 Срок: {expire_days} дней\n"
            f"🔑 UUID: `{vless_uuid[:8]}...{vless_uuid[-4:]}`\n\n"
        )

        if api_success:
            result_message += "✅ Создан в Hiddify Panel"
        else:
            result_message += "⚠️ Создан только в локальной БД (API недоступен)"

        bot.send_message(
            telegram_id,
            result_message,
            parse_mode='Markdown',
            reply_markup=admin_main_keyboard()
        )

        logger.info(f"Admin {telegram_id} created user: {username} (ID: {user_id})")

    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        clear_user_state(telegram_id)
        bot.answer_callback_query(call.id, "Ошибка создания", show_alert=True)
        bot.send_message(
            telegram_id,
            f"❌ Ошибка создания пользователя: {e}",
            parse_mode='Markdown',
            reply_markup=admin_main_keyboard()
        )


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

    # Проверка прав на приглашение (v3.1.1)
    if can_invite_users and not can_invite_users(telegram_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для этой операции")
        return

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
# CALLBACK HANDLERS - УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ============================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('user_info_'))
def handle_user_info(call):
    """Показать информацию о пользователе"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return

    user_id = int(call.data.split('_')[2])

    user = get_user(user_id)
    if not user:
        bot.answer_callback_query(call.id, "Пользователь не найден", show_alert=True)
        return

    info = (
        f"📋 *Информация о пользователе*\n\n"
        f"ID: {user['id']}\n"
        f"Telegram: @{user.get('telegram_username', 'N/A')}\n"
        f"Имя: {user.get('telegram_first_name', 'N/A')}\n"
        f"Тип: {user.get('user_type', 'private')}\n\n"
        f"📦 Лимит: {user['data_limit_bytes'] / (1024**3):.0f} GB\n"
        f"📅 Истекает: {user.get('expires_at', 'Бессрочно')}\n\n"
        f"✅ Активен: {'Да' if user['is_active'] else 'Нет'}\n"
        f"🔒 Заблокирован: {'Да' if user['is_blocked'] else 'Нет'}\n"
    )

    bot.send_message(telegram_id, info, parse_mode='Markdown')
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_extend_'))
def handle_user_extend(call):
    """Продлить подписку пользователю"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return

    user_db_id = int(call.data.split('_')[2])

    # Продлеваем на 30 дней по умолчанию
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем текущую дату истечения
    cursor.execute('SELECT expires_at FROM users WHERE id = ?', (user_db_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        bot.answer_callback_query(call.id, "Пользователь не найден", show_alert=True)
        return

    current_expire = row[0]

    # Если даты нет или истекла - от сегодня, иначе от текущей даты
    if not current_expire:
        base_date = datetime.now()
    else:
        try:
            base_date = datetime.fromisoformat(current_expire)
            if base_date < datetime.now():
                base_date = datetime.now()
        except:
            base_date = datetime.now()

    new_expire = base_date + timedelta(days=30)

    cursor.execute('UPDATE users SET expires_at = ? WHERE id = ?', (new_expire.isoformat(), user_db_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Продлено на 30 дней")
    logger.info(f"Admin {telegram_id} extended user {user_db_id} until {new_expire}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_block_'))
def handle_user_block(call):
    """Заблокировать/разблокировать пользователя"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return

    user_db_id = int(call.data.split('_')[2])

    # Переключаем статус блокировки
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT is_blocked FROM users WHERE id = ?', (user_db_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        bot.answer_callback_query(call.id, "Пользователь не найден", show_alert=True)
        return

    current_status = row[0]
    new_status = not current_status

    cursor.execute('UPDATE users SET is_blocked = ? WHERE id = ?', (new_status, user_db_id))
    conn.commit()
    conn.close()

    action = "заблокирован" if new_status else "разблокирован"
    bot.answer_callback_query(call.id, f"Пользователь {action}")
    logger.info(f"Admin {telegram_id} {'blocked' if new_status else 'unblocked'} user {user_db_id}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_delete_'))
def handle_user_delete(call):
    """Удалить пользователя"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return

    user_db_id = int(call.data.split('_')[2])

    # Удаляем из БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (user_db_id,))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Пользователь удалён")
    bot.send_message(
        telegram_id,
        "🗑️ Пользователь удалён",
        reply_markup=admin_main_keyboard()
    )
    logger.info(f"Admin {telegram_id} deleted user {user_db_id}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_limit_'))
def handle_user_limit(call):
    """Изменить лимит трафика"""


# ============================================================================
# v4.0: MESSAGE HANDLERS FOR NEW FEATURES
# ============================================================================

@bot.message_handler(func=lambda message: message.text == "💳 Купить подписку" if V4_AVAILABLE else False)
def handle_buy_subscription_button(message):
    """Обработка кнопки 'Купить подписку'"""
    if not V4_AVAILABLE:
        return

    # Имитируем callback query для использования тех же handlers
    class FakeCallback:
        def __init__(self, chat, from_user):
            self.message = chat
            self.id = None
            self.from_user = from_user
            self.data = "buy_subscription"

    fake_call = FakeCallback(message.chat, message.from_user)
    from v4_handlers import handle_buy_subscription
    handle_buy_subscription(fake_call)


@bot.message_handler(commands=['support'])
def handle_support_command(message):
    """Команда /support - создать тикет"""
    if not V4_AVAILABLE:
        bot.send_message(message.chat.id, "❌ Поддержка временно недоступна")
        return

    # Используем обработчик из v4_handlers
    from v4_handlers import handle_support_command
    handle_support_command(message)


@bot.message_handler(func=lambda message: message.text == "💬 Поддержка" if V4_AVAILABLE else False)
def handle_support_button(message):
    """Обработка кнопки 'Поддержка'"""
    if not V4_AVAILABLE:
        return

    # Вызываем команду /support
    handle_support_command(message)


@bot.message_handler(func=lambda message: message.text == "👥 Рефералы" if V4_AVAILABLE else False)
def handle_referrals_button(message):
    """Обработка кнопки 'Рефералы'"""
    if not V4_AVAILABLE:
        return

    # Имитируем callback query
    class FakeCallback:
        def __init__(self, chat, from_user):
            self.message = chat
            self.id = None
            self.from_user = from_user
            self.data = "my_referrals"

    fake_call = FakeCallback(message.chat, message.from_user)
    from v4_handlers import handle_my_referrals
    handle_my_referrals(fake_call)


@bot.message_handler(commands=['referrals', 'ref'])
def handle_referrals_command(message):
    """Команда /referrals - статистика рефералов"""
    if not V4_AVAILABLE:
        bot.send_message(message.chat.id, "❌ Рефералы временно недоступны")
        return

    handle_referrals_button(message)


# ============================================================================
# КОНЕЦ v4.0 MESSAGE HANDLERS
# ============================================================================

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return

    user_db_id = int(call.data.split('_')[2])

    # Увеличиваем лимит на 50 GB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT data_limit_bytes FROM users WHERE id = ?', (user_db_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        bot.answer_callback_query(call.id, "Пользователь не найден", show_alert=True)
        return

    current_limit = row[0]
    new_limit = current_limit + (50 * 1024**3)  # +50 GB

    cursor.execute('UPDATE users SET data_limit_bytes = ? WHERE id = ?', (new_limit, user_db_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, f"Лимит увеличен на 50 GB")
    logger.info(f"Admin {telegram_id} increased limit for user {user_db_id} to {new_limit / (1024**3):.0f} GB")


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

    # v4.0: Инициализация новых модулей
    if V4_AVAILABLE:
        logger.info("Инициализация v4.0 модулей...")
        import asyncio
        try:
            asyncio.run(init_v4_modules())
            # Регистрация v4.0 handlers
            register_all_v4_handlers(bot)
            logger.info("✅ v4.0 модули загружены")
        except Exception as e:
            logger.warning(f"⚠️  Ошибка инициализации v4.0 модулей: {e}")
    else:
        logger.info("v4.0 модули недоступны, работаем в режиме совместимости")

    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
