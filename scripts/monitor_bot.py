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
