#!/usr/bin/env python3
"""
Hiddify Manager Telegram Bot v2.0
Полнофункциональный бот с UI/UX для приватных пользователей и админки
"""

import os
import sys
import sqlite3
import logging
import uuid
import json
from datetime import datetime, timedelta
from functools import wraps
from telebot import TeleBot, types
from dotenv import load_dotenv

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
            ss2022_password VARCHAR(255)
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
            'hysteria2_password', 'ss2022_password'
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


def validate_invite_code(invite_code: str) -> dict:
    """
    Проверить валидность инвайт-кода

    Args:
        invite_code: Инвайт-код для проверки

    Returns:
        dict: {'valid': bool, 'inviter_id': int, 'invite_id': int, 'error': str}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, created_by, max_uses, used_count, expires_at, is_active
        FROM invites
        WHERE code = ?
    ''', (invite_code,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return {'valid': False, 'error': 'Инвайт-код не найден'}

    invite_id, created_by, max_uses, used_count, expires_at, is_active = result

    # Проверка активности
    if not is_active:
        return {'valid': False, 'error': 'Инвайт-код деактивирован'}

    # Проверка лимита использований
    if used_count >= max_uses:
        return {'valid': False, 'error': 'Инвайт-код уже использован максимальное число раз'}

    # Проверка срока действия
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)
            if datetime.now() > expiry:
                return {'valid': False, 'error': 'Срок действия инвайт-кода истёк'}
        except ValueError:
            logger.warning(f"Некорректная дата истечения для инвайта {invite_code}")
            return {'valid': False, 'error': 'Некорректный инвайт-код'}

    return {
        'valid': True,
        'inviter_id': created_by,
        'invite_id': invite_id
    }


def increment_invite_usage(invite_id: int) -> bool:
    """
    Увеличить счётчик использований инвайта

    Args:
        invite_id: ID инвайта

    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE invites
            SET used_count = used_count + 1
            WHERE id = ?
        ''', (invite_id,))

        conn.commit()
        conn.close()

        logger.info(f"Инвайт {invite_id} использован")
        return True

    except Exception as e:
        logger.error(f"Ошибка при увеличении счётчика инвайта: {e}")
        return False


def log_connection(user_id: int, protocol: str, action: str,
                   location_city: str = None, location_country: str = None,
                   ip_address: str = None) -> bool:
    """
    Логировать подключение/отключение пользователя

    Args:
        user_id: ID пользователя
        protocol: Протокол подключения (vless, hysteria2, ss2022)
        action: Действие (connect, disconnect, update)
        location_city: Город (опционально)
        location_country: Страна (опционально)
        ip_address: IP адрес (опционально)

    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if action == 'connect':
            # Создать новую запись подключения
            cursor.execute('''
                INSERT INTO connections (
                    user_id, protocol, location_city, location_country,
                    ip_address, connected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id, protocol, location_city, location_country,
                ip_address, datetime.now().isoformat()
            ))

        elif action == 'disconnect':
            # Обновить существующее подключение
            cursor.execute('''
                UPDATE connections
                SET disconnected_at = ?
                WHERE user_id = ? AND protocol = ?
                AND disconnected_at IS NULL
                ORDER BY connected_at DESC
                LIMIT 1
            ''', (datetime.now().isoformat(), user_id, protocol))

        elif action == 'update':
            # Обновить трафик (если есть данные)
            # Для будущего использования с Xray/3X-ui API
            pass

        conn.commit()
        conn.close()

        logger.info(f"Логирование: user {user_id} {action} ({protocol})")
        return True

    except Exception as e:
        logger.error(f"Ошибка при логировании подключения: {e}")
        return False


def update_connection_traffic(user_id: int, bytes_sent: int, bytes_received: int) -> bool:
    """
    Обновить статистику трафика для активного подключения

    Args:
        user_id: ID пользователя
        bytes_sent: Отправлено байт
        bytes_received: Получено байт

    Returns:
        bool: True если успешно
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE connections
            SET bytes_sent = ?, bytes_received = ?
            WHERE user_id = ? AND disconnected_at IS NULL
            ORDER BY connected_at DESC
            LIMIT 1
        ''', (bytes_sent, bytes_received, user_id))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        logger.error(f"Ошибка при обновлении трафика: {e}")
        return False


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
    btn2 = types.KeyboardButton("🎫 Инвайты")
    btn3 = types.KeyboardButton("➕ Создать юзера")
    btn4 = types.KeyboardButton("📈 Статистика")
    btn5 = types.KeyboardButton("⚙️ Настройки")
    btn6 = types.KeyboardButton("📢 Рассылка")
    btn7 = types.KeyboardButton("🔧 Сервер")
    btn8 = types.KeyboardButton("🚪 Выход")

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)

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
            validation = validate_invite_code(invite_code)

            if not validation['valid']:
                bot.send_message(
                    telegram_id,
                    f"❌ *{validation['error']}*\n\n"
                    "Для регистрации нужен действительный инвайт-код.\n"
                    "Обратитесь к администратору.",
                    parse_mode='Markdown'
                )
                return

            # Создать пользователя с привязкой к инвайтеру
            user_id = create_user(
                telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                invited_by=validation['inviter_id']
            )

            if user_id:
                # Увеличить счётчик использований инвайта
                increment_invite_usage(validation['invite_id'])

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
            # Без инвайта - только для админа
            if telegram_id == ADMIN_ID:
                user_id = create_user(
                    telegram_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name
                )
                if user_id:
                    bot.send_message(
                        telegram_id,
                        "👑 *Администратор создан*\n\n"
                        "Добро пожаловать в панель управления!",
                        parse_mode='Markdown',
                        reply_markup=admin_main_keyboard()
                    )
                else:
                    bot.send_message(
                        telegram_id,
                        "❌ Ошибка создания администратора."
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получить последние подключения
    cursor.execute('''
        SELECT protocol, location_city, location_country,
               connected_at, disconnected_at,
               bytes_sent, bytes_received
        FROM connections
        WHERE user_id = ?
        ORDER BY connected_at DESC
        LIMIT 10
    ''', (user['id'],))

    connections = cursor.fetchall()
    conn.close()

    if not connections:
        bot.send_message(
            telegram_id,
            "📱 *Мои устройства*\n\n"
            "Пока нет записей о подключениях.\n\n"
            "Нажмите 'Получить ключ' для подключения.",
            parse_mode='Markdown'
        )
        return

    # Формировать список устройств
    response = "📱 *Мои устройства*\n\n"
    response += "Последние подключения:\n\n"

    for i, conn_data in enumerate(connections, 1):
        protocol, city, country, connected_at, disconnected_at, sent, received = conn_data

        # Определить статус
        is_active = disconnected_at is None
        status = "🟢 Онлайн" if is_active else "⚫ Офлайн"

        # Локация
        location = f"{city}, {country}" if city and country else "Неизвестно"

        # Время
        try:
            conn_time = datetime.fromisoformat(connected_at)
            time_str = f"{conn_time.strftime('%d.%m %H:%M')}"
        except (ValueError, TypeError):
            time_str = "Неизвестно"

        # Трафик
        traffic_gb = (sent + received) / (1024**3)

        # Название устройства (по протоколу)
        device_names = {
            'vless': '📱 Устройство (VLESS)',
            'hysteria2': '📱 Устройство (Hysteria2)',
            'ss2022': '📱 Устройство (SS-2022)',
            'reality': '📱 Устройство (Reality)',
            None: '📱 Устройство'
        }
        device_name = device_names.get(protocol, '📱 Устройство')

        # Формируем строку устройства
        response += f"{i}. {device_name}\n"
        response += f"   📍 {location}\n"
        response += f"   {status} | {time_str}\n"
        response += f"   📊 Трафик: {traffic_gb:.2f} GB\n\n"

    # Кнопка обновления
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_devices"))

    bot.send_message(
        telegram_id,
        response,
        parse_mode='Markdown',
        reply_markup=markup
    )


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
    """Обработка кнопки 'Моя подписка'"""

    telegram_id = message.chat.id
    user = get_user(telegram_id)

    if not user:
        return

    # Расчёт процента использования трафика
    used_percent = (user['used_bytes'] / user['data_limit_bytes']) * 100
    used_gb = user['used_bytes'] / (1024**3)
    limit_gb = user['data_limit_bytes'] / (1024**3)

    # Формирование строки даты истечения
    expire_str = "Бессрочно"
    if user['expires_at']:
        expire_date = datetime.fromisoformat(user['expires_at'])
        days_left = (expire_date - datetime.now()).days
        expire_str = expire_date.strftime("%d.%m.%Y")

    response = (
        f"📊 *Моя подписка*\n\n"
        f"Статус: ✅ Активен\n\n"
        f"Тип: Приватный\n"
        f"Истекает: {expire_str} (осталось {days_left} дней)\n\n"
        f"Лимит трафика:\n"
        f"{used_percent:.1f}% - {used_gb:.1f} GB / {limit_gb:.0f} GB\n\n"
        f"Протоколы:\n"
        f"{'✅' if user['vless_enabled'] else '❌'} VLESS-Reality\n"
        f"{'✅' if user['hysteria2_enabled'] else '❌'} Hysteria2\n"
        f"{'✅' if user['ss2022_enabled'] else '❌'} Shadowsocks-2022"
    )

    bot.send_message(telegram_id, response, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "💬 Поддержка")
def handle_support(message):
    """Обработка кнопки 'Поддержка'"""

    telegram_id = message.chat.id

    markup = types.InlineKeyboardMarkup(row_width=1)

    btn1 = types.InlineKeyboardButton(
        "❓ Как подключить? 📱",
        callback_data="support_guide"
    )
    btn2 = types.InlineKeyboardButton(
        "❓ Медленная скорость? 🐌",
        callback_data="support_speed"
    )
    btn3 = types.InlineKeyboardButton(
        "❓ Не работает? 🔧",
        callback_data="support_troubleshoot"
    )

    markup.add(btn1, btn2, btn3)

    bot.send_message(
        telegram_id,
        "💬 *Поддержка*\n\n"
        "Частые вопросы:",
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, telegram_id, telegram_username, telegram_first_name,
               is_active, is_blocked, expires_at, used_bytes,
               created_at, user_type
        FROM users
        ORDER BY created_at DESC
        LIMIT 10
    ''')

    users = cursor.fetchall()

    # Получить статистику
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
    active_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
    blocked_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users')
    total_count = cursor.fetchone()[0]

    conn.close()

    if not users:
        bot.send_message(
            telegram_id,
            "👥 *Пользователи*\n\n"
            "Пользователей пока нет.",
            parse_mode='Markdown'
        )
        return

    response = f"👥 *Список пользователей* (первые 10)\n\n"
    response += f"Всего: {total_count} | Активных: {active_count} | Заблокировано: {blocked_count}\n\n"

    # Отправляем каждого пользователя отдельно с кнопками управления
    for user in users:
        user_id, tg_id, username, first_name, is_active, is_blocked, expires, used, created, user_type = user

        # Статус
        if is_blocked:
            status = "🔒"
        elif not is_active:
            status = "⚪"
        else:
            status = "✅"

        # Имя
        name = first_name or username or f"User_{user_id}"
        username_str = f"@{username}" if username else ""

        # Трафик
        used_gb = used / (1024**3)

        # Срок
        expiry_info = ""
        if expires:
            try:
                expire_date = datetime.fromisoformat(expires)
                if expire_date > datetime.now():
                    days_left = (expire_date - datetime.now()).days
                    expiry_info = f" ({days_left} дн)"
                else:
                    expiry_info = " (истёк)"
            except ValueError:
                pass

        user_response = f"{status} *{name}* {username_str}\n"
        user_response += f"ID: {user_id} | TG: {tg_id}\n"
        user_response += f"Трафик: {used_gb:.2f} GB{expiry_info}"

        # Inline клавиатура для управления пользователем
        markup = types.InlineKeyboardMarkup(row_width=2)

        btn_info = types.InlineKeyboardButton("ℹ️ Инфо", callback_data=f"user_info_{user_id}")
        btn_extend = types.InlineKeyboardButton("📅 Продлить", callback_data=f"user_extend_{user_id}")
        btn_limit = types.InlineKeyboardButton("📊 Лимит", callback_data=f"user_limit_{user_id}")

        if is_blocked:
            btn_block = types.InlineKeyboardButton("🔓 Разблокировать", callback_data=f"user_unblock_{user_id}")
        else:
            btn_block = types.InlineKeyboardButton("🔒 Заблокировать", callback_data=f"user_block_{user_id}")

        markup.add(btn_info, btn_extend)
        markup.add(btn_limit, btn_block)

        bot.send_message(
            telegram_id,
            user_response,
            parse_mode='Markdown',
            reply_markup=markup
        )

    # Кнопки навигации
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔄 Обновить", callback_data="users_refresh")
    btn2 = types.InlineKeyboardButton("📊 Статистика", callback_data="stats_main")
    markup.add(btn1, btn2)

    bot.send_message(
        telegram_id,
        "_Навигация:_",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == "➕ Создать юзера")
def handle_admin_create_user(message):
    """Обработка кнопки 'Создать юзера' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    bot.send_message(
        telegram_id,
        "➕ *Создать пользователя*\n\n"
        "Шаг 1 из 2: Введите username Telegram\n\n"
        "Пример: @username\n\n"
        "Или отправьте forward сообщения от пользователя",
        parse_mode='Markdown'
    )

    bot.register_next_step_handler(message, process_create_user_username)


def process_create_user_username(message):
    """Обработка ввода username при создании пользователя"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    username = message.text

    # Валидация
    if not username.startswith('@'):
        bot.send_message(
            telegram_id,
            "❌ Username должен начинаться с @\n\n"
            "Попробуйте ещё раз:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(message, process_create_user_username)
        return

    # TODO: Запрос параметров (лимит, срок)
    # Временное создание с дефолтными значениями
    bot.send_message(
        telegram_id,
        f"✅ Пользователь {username} создан!\n\n"
        f"(функционал в разработке)",
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "🎫 Инвайты")
def handle_admin_invites(message):
    """Обработка кнопки 'Инвайты' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    # Получить список инвайтов из БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT code, max_uses, used_count, is_active, expires_at
        FROM invites
        ORDER BY created_at DESC
        LIMIT 10
    ''')

    invites = cursor.fetchall()
    conn.close()

    if not invites:
        response = "🎫 *Инвайт-коды*\n\n"
        response += "Инвайтов пока нет. Создайте первый!"
    else:
        response = f"🎫 *Инвайт-коды* (последние 10)\n\n"

        for invite in invites:
            code, max_uses, used_count, is_active, expires_at = invite

            status = "✅" if is_active else "❌"
            expires_str = ""
            if expires_at:
                try:
                    expire_date = datetime.fromisoformat(expires_at)
                    if expire_date > datetime.now():
                        days_left = (expire_date - datetime.now()).days
                        expires_str = f" (истекает через {days_left} дн)"
                    else:
                        expires_str = " (истёк)"
                        status = "❌"
                except ValueError:
                    pass

            response += f"{status} `{code}`\n"
            response += f"   Использований: {used_count}/{max_uses}{expires_str}\n\n"

    # Inline клавиатура для управления
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_create = types.InlineKeyboardButton("➕ Создать инвайты", callback_data="invites_create")
    btn_list = types.InlineKeyboardButton("📋 Все инвайты", callback_data="invites_list_all")
    btn_back = types.InlineKeyboardButton("◀️ Назад", callback_data="invites_back")

    markup.add(btn_create, btn_list)
    markup.add(btn_back)

    bot.send_message(
        telegram_id,
        response,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == "📈 Статистика")
def handle_admin_stats(message):
    """Обработка кнопки 'Статистика' (админ)"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Количество пользователей
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
    active_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
    blocked_users = cursor.fetchone()[0]

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= ?', (today_start,))
    new_today = cursor.fetchone()[0]

    # Трафик
    cursor.execute('SELECT SUM(used_bytes) FROM users WHERE is_active = 1')
    total_used = cursor.fetchone()[0] or 0
    total_used_gb = total_used / (1024**3)

    # Trial
    cursor.execute('SELECT COUNT(*) FROM users WHERE user_type = "trial"')
    trial_users = cursor.fetchone()[0]

    # Инвайты
    cursor.execute('SELECT COUNT(*) FROM invites WHERE is_active = 1')
    active_invites = cursor.fetchone()[0]

    cursor.execute('SELECT SUM(used_count), SUM(max_uses) FROM invites WHERE is_active = 1')
    invite_usage = cursor.fetchone()
    invite_used = invite_usage[0] or 0
    invite_total = invite_usage[1] or 0

    conn.close()

    response = "📈 *Статистика*\n\n"

    response += "👥 *Пользователи:*\n"
    response += f"Активных: {active_users}\n"
    response += f"Заблокировано: {blocked_users}\n"
    response += f"Новых сегодня: {new_today}\n"
    response += f"Пробный период: {trial_users}\n\n"

    response += "📊 *Трафик:*\n"
    response += f"Общий: {total_used_gb:.2f} GB\n\n"

    response += "🎫 *Инвайты:*\n"
    response += f"Активных: {active_invites}\n"
    if invite_total > 0:
        invite_percent = (invite_used / invite_total) * 100
        response += f"Использовано: {invite_used}/{invite_total} ({invite_percent:.1f}%)\n"
    else:
        response += f"Использовано: {invite_used}/{invite_total}\n"

    bot.send_message(
        telegram_id,
        response,
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('protocol_'))
def handle_protocol_selection(call):
    """Обработка выбора протокола"""

    telegram_id = call.message.chat.id
    protocol = call.data.split('_')[1]

    user = get_user(telegram_id)

    if not user:
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return

    # TODO: Генерация конфига для выбранного протокола
    if protocol == 'vless':
        config_link = f"https://{PANEL_DOMAIN}/sub/{user['vless_uuid']}"
        config_name = "VLESS-Reality"
    elif protocol == 'hysteria2':
        config_link = f"hysteria2://{user['hysteria2_password']}@{PANEL_DOMAIN}:443/?sni={PANEL_DOMAIN}"
        config_name = "Hysteria2"
    else:
        config_link = f"ss2022://{user['ss2022_password']}@{PANEL_DOMAIN}:8388"
        config_name = "Shadowsocks-2022"

    bot.send_message(
        telegram_id,
        f"📋 *Конфигурация: {config_name}*\n\n"
        f"```json\n{config_link}\n```\n\n"
        f"Импортируйте этот конфиг в ваш клиент.",
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, "Конфигурация отправлена")


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


@bot.callback_query_handler(func=lambda call: call.data.startswith('support_'))
def handle_support_callbacks(call):
    """Обработка кнопок поддержки"""

    action = call.data.split('_')[1]

    responses = {
        'guide': "📱 *Как подключить?*\n\n1. Нажмите 'Получить ключ'\n2. Выберите протокол (VLESS-Reality)\n3. Скачайте клиент: V2Ray/Xray/Qv2ray\n4. Импортируйте конфиг\n5. Подключитесь",
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
# CALLBACK HANDLERS - ИНВАЙТЫ (АДМИНКА)
# ============================================================================

@bot.callback_query_handler(func=lambda call: call.data == 'invites_create')
def handle_invites_create(call):
    """Обработка кнопки 'Создать инвайты'"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    # Показать меню выбора количества
    markup = types.InlineKeyboardMarkup(row_width=3)

    quantities = [1, 5, 10, 20, 50]
    buttons = []

    for qty in quantities:
        buttons.append(
            types.InlineKeyboardButton(f"{qty} шт", callback_data=f"invites_qty_{qty}")
        )

    # Добавить кнопки по 3 в ряд
    for i in range(0, len(buttons), 3):
        markup.row(*buttons[i:i+3])

    # Кнопка "Другое количество"
    markup.add(types.InlineKeyboardButton("✏️ Другое", callback_data="invites_qty_custom"))

    bot.edit_message_text(
        "➕ *Создать инвайты*\n\n"
        "Выберите количество:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('invites_qty_'))
def handle_invites_quantity(call):
    """Обработка выбора количества инвайтов"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    if call.data == 'invites_qty_custom':
        # Запросить своё количество
        msg = bot.send_message(
            telegram_id,
            "✏️ Введите количество инвайтов (от 1 до 100):"
        )
        bot.register_next_step_handler(msg, process_invites_custom_qty)
        bot.answer_callback_query(call.id)
        return

    # Извлечь количество
    qty = int(call.data.split('_')[2])

    # Показать выбор срока действия
    markup = types.InlineKeyboardMarkup(row_width=3)

    durations = [
        ("7 дней", 7),
        ("30 дней", 30),
        ("90 дней", 90),
        ("Бессрочно", None)
    ]

    for label, days in durations:
        callback = f"invites_create_{qty}_{days if days else 'unlimited'}"
        markup.add(types.InlineKeyboardButton(label, callback_data=callback))

    markup.add(types.InlineKeyboardButton("◀️ Отмена", callback_data="invites_cancel"))

    bot.edit_message_text(
        f"➕ *Создать {qty} инвайтов*\n\n"
        "Выберите срок действия:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


def process_invites_custom_qty(message):
    """Обработка ввода своего количества инвайтов"""

    telegram_id = message.chat.id

    if not is_admin(telegram_id):
        return

    try:
        qty = int(message.text)
        if qty < 1 or qty > 100:
            bot.send_message(
                telegram_id,
                "❌ Количество должно быть от 1 до 100",
                reply_markup=admin_main_keyboard()
            )
            return
    except ValueError:
        bot.send_message(
            telegram_id,
            "❌ Некорректное число. Попробуйте ещё раз через меню 'Инвайты'",
            reply_markup=admin_main_keyboard()
        )
        return

    # Показать выбор срока действия
    markup = types.InlineKeyboardMarkup(row_width=3)

    durations = [
        ("7 дней", 7),
        ("30 дней", 30),
        ("90 дней", 90),
        ("Бессрочно", None)
    ]

    for label, days in durations:
        callback = f"invites_create_{qty}_{days if days else 'unlimited'}"
        markup.add(types.InlineKeyboardButton(label, callback_data=callback))

    markup.add(types.InlineKeyboardButton("◀️ Отмена", callback_data="invites_cancel"))

    bot.send_message(
        telegram_id,
        f"➕ *Создать {qty} инвайтов*\n\n"
        "Выберите срок действия:",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('invites_create_'))
def handle_invites_create_final(call):
    """Финальное создание инвайтов"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    # Извлечь параметры: qty_days
    params = call.data.split('_')[2:]  # ['qty', 'days']
    qty = int(params[0])
    days_str = params[1]

    days = None if days_str == 'unlimited' else int(days_str)

    # Создать инвайты
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получить ID админа как created_by
    cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()

    if not result:
        bot.answer_callback_query(call.id, "Ошибка: вы не найдены в БД")
        conn.close()
        return

    admin_id = result[0]

    invites_created = []
    for _ in range(qty):
        code = f"INV_{os.urandom(8).hex()}"
        expires_at = None
        if days:
            expires_at = (datetime.now() + timedelta(days=days)).isoformat()

        cursor.execute('''
            INSERT INTO invites (code, created_by, max_uses, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (code, admin_id, 1, expires_at))

        invites_created.append(code)

    conn.commit()
    conn.close()

    # Формировать ответ
    response = f"✅ *Создано {qty} инвайт-кодов*\n\n"

    if days:
        response += f"Срок действия: {days} дней\n\n"

    response += "Список кодов:\n\n"
    for code in invites_created[:5]:  # Показать первые 5
        response += f"`{code}`\n"

    if len(invites_created) > 5:
        response += f"\n... и ещё {len(invites_created) - 5} кодов"

    response += "\n\nДля использования:"
    response += f"\nhttps://t.me/{bot.get_me().username}?start=КОД"

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, f"Создано {qty} инвайтов")


@bot.callback_query_handler(func=lambda call: call.data == 'invites_list_all')
def handle_invites_list_all(call):
    """Показать все инвайты"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM invites')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT code, max_uses, used_count, is_active, expires_at, created_at
        FROM invites
        ORDER BY created_at DESC
    ''')

    invites = cursor.fetchall()
    conn.close()

    if not invites:
        bot.edit_message_text(
            "🎫 *Инвайты*\n\nПока нет инвайтов.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return

    response = f"🎫 *Все инвайты* ({total})\n\n"

    for invite in invites[:20]:  # Максимум 20 для одного сообщения
        code, max_uses, used_count, is_active, expires_at, created_at = invite

        status = "✅" if is_active else "❌"
        expires_str = ""

        if expires_at:
            try:
                expire_date = datetime.fromisoformat(expires_at)
                if expire_date > datetime.now():
                    days_left = (expire_date - datetime.now()).days
                    expires_str = f" ({days_left} дн)"
                else:
                    expires_str = " (истёк)"
                    status = "❌"
            except ValueError:
                pass

        response += f"{status} `{code}` - {used_count}/{max_uses}{expires_str}\n"

    if len(invites) > 20:
        response += f"\n... и ещё {len(invites) - 20} инвайтов"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="invites_back"))

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data in ['invites_back', 'invites_cancel'])
def handle_invites_back(call):
    """Вернуться в главное меню инвайтов"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    # Перезапустить handle_admin_invites
    call.message.text = "🎫 Инвайты"
    handle_admin_invites(call.message)

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'refresh_devices')
def handle_refresh_devices(call):
    """Обновить список устройств"""

    # Повторный вызов handle_my_devices
    call.message.text = "📱 Мои устройства"
    handle_my_devices(call.message)
    bot.answer_callback_query(call.id, "Устройства обновлены")


# ============================================================================
# CALLBACK HANDLERS - УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (АДМИНКА)
# ============================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('user_info_'))
def handle_user_info(call):
    """Показать детальную информацию о пользователе"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    user_id = int(call.data.split('_')[2])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return

    columns = [
        'id', 'telegram_id', 'telegram_username', 'telegram_first_name',
        'user_type', 'invite_code', 'invited_by', 'data_limit_bytes',
        'expire_days', 'created_at', 'expires_at', 'used_bytes',
        'last_connection', 'is_active', 'is_blocked', 'vless_enabled',
        'hysteria2_enabled', 'ss2022_enabled', 'vless_uuid',
        'hysteria2_password', 'ss2022_password'
    ]

    user_dict = dict(zip(columns, user))
    conn.close()

    response = f"ℹ️ *Пользователь ID:{user_id}*\n\n"
    response += f"Telegram: @{user_dict['telegram_username']} ({user_dict['telegram_first_name']})\n"
    response += f"ID: {user_dict['telegram_id']}\n"
    response += f"Тип: {user_dict['user_type']}\n\n"

    response += "*Статус:*\n"
    response += f"Активен: {'✅' if user_dict['is_active'] else '❌'}\n"
    response += f"Заблокирован: {'⛔' if user_dict['is_blocked'] else '✅'}\n\n"

    response += "*Лимиты:*\n"
    used_gb = user_dict['used_bytes'] / (1024**3)
    limit_gb = user_dict['data_limit_bytes'] / (1024**3)
    response += f"Трафик: {used_gb:.2f} GB / {limit_gb:.0f} GB\n"

    if user_dict['expires_at']:
        try:
            expire_date = datetime.fromisoformat(user_dict['expires_at'])
            days_left = (expire_date - datetime.now()).days
            response += f"Истекает: {expire_date.strftime('%d.%m.%Y')} ({days_left} дн)\n"
        except ValueError:
            pass

    response += f"\n*Протоколы:*\n"
    response += f"VLESS: {'✅' if user_dict['vless_enabled'] else '❌'}\n"
    response += f"Hysteria2: {'✅' if user_dict['hysteria2_enabled'] else '❌'}\n"
    response += f"SS-2022: {'✅' if user_dict['ss2022_enabled'] else '❌'}\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="users_refresh"))

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_extend_'))
def handle_user_extend(call):
    """Продлить подписку пользователю"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    user_id = int(call.data.split('_')[2])

    # Показать выбор периода
    markup = types.InlineKeyboardMarkup(row_width=3)

    periods = [
        ("7 дней", 7),
        ("30 дней", 30),
        ("90 дней", 90),
        ("180 дней", 180),
        ("365 дней", 365),
    ]

    for label, days in periods:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"user_extend_confirm_{user_id}_{days}"))

    markup.add(types.InlineKeyboardButton("◀️ Отмена", callback_data="users_refresh"))

    bot.edit_message_text(
        f"📅 *Продлить подписку*\n\n"
        f"Пользователь ID: {user_id}\n"
        f"Выберите период:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_extend_confirm_'))
def handle_user_extend_confirm(call):
    """Подтверждение продления подписки"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    params = call.data.split('_')
    user_id = int(params[3])
    days = int(params[4])

    # Получить текущую дату истечения
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT expires_at FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return

    current_expires = result[0]

    # Новая дата
    if current_expires:
        try:
            new_expires = datetime.fromisoformat(current_expires) + timedelta(days=days)
        except ValueError:
            new_expires = datetime.now() + timedelta(days=days)
    else:
        new_expires = datetime.now() + timedelta(days=days)

    # Обновить
    cursor.execute(
        'UPDATE users SET expires_at = ? WHERE id = ?',
        (new_expires.isoformat(), user_id)
    )

    conn.commit()
    conn.close()

    bot.edit_message_text(
        f"✅ *Подписка продлена*\n\n"
        f"Пользователь ID: {user_id}\n"
        f"Период: +{days} дней\n"
        f"Новая дата: {new_expires.strftime('%d.%m.%Y')}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, "Подписка продлена")


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_block_'))
def handle_user_block(call):
    """Заблокировать пользователя"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    user_id = int(call.data.split('_')[2])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET is_blocked = 1 WHERE id = ?', (user_id,))

    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Пользователь заблокирован")

    # Обновить сообщение
    call.message.text = "👥 Пользователи"
    handle_admin_users(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_unblock_'))
def handle_user_unblock(call):
    """Разблокировать пользователя"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    user_id = int(call.data.split('_')[2])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET is_blocked = 0 WHERE id = ?', (user_id,))

    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Пользователь разблокирован")

    # Обновить сообщение
    call.message.text = "👥 Пользователи"
    handle_admin_users(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_limit_'))
def handle_user_limit(call):
    """Изменить лимит трафика"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    user_id = int(call.data.split('_')[2])

    # Показать выбор лимита
    markup = types.InlineKeyboardMarkup(row_width=2)

    limits = [
        ("50 GB", 50 * 1024**3),
        ("100 GB", 100 * 1024**3),
        ("200 GB", 200 * 1024**3),
        ("500 GB", 500 * 1024**3),
        ("1 TB", 1024**4),
        ("Безлимит", -1),
    ]

    for label, bytes_val in limits:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"user_limit_confirm_{user_id}_{bytes_val}"))

    markup.add(types.InlineKeyboardButton("◀️ Отмена", callback_data="users_refresh"))

    bot.edit_message_text(
        f"📊 *Изменить лимит*\n\n"
        f"Пользователь ID: {user_id}\n"
        f"Выберите лимит:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user_limit_confirm_'))
def handle_user_limit_confirm(call):
    """Подтверждение изменения лимита"""

    telegram_id = call.message.chat.id

    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "Доступ запрещён")
        return

    params = call.data.split('_')
    user_id = int(params[3])
    bytes_val = int(params[4])

    # Преобразовать -1 в безлимит (10 TB)
    if bytes_val == -1:
        bytes_val = 10 * 1024**4
        limit_label = "Безлимит"
    else:
        limit_gb = bytes_val / (1024**3)
        limit_label = f"{limit_gb:.0f} GB"

    # Обновить
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        'UPDATE users SET data_limit_bytes = ? WHERE id = ?',
        (bytes_val, user_id)
    )

    conn.commit()
    conn.close()

    bot.edit_message_text(
        f"✅ *Лимит изменён*\n\n"
        f"Пользователь ID: {user_id}\n"
        f"Новый лимит: {limit_label}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, "Лимит изменён")


@bot.callback_query_handler(func=lambda call: call.data in ['users_refresh', 'stats_main'])
def handle_users_refresh(call):
    """Обновить список пользователей"""

    call.message.text = "👥 Пользователи"
    handle_admin_users(call.message)
    bot.answer_callback_query(call.id, "Список обновлён")


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
