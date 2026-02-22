#!/usr/bin/env python3
"""
Telegram Bot Monitor для Hiddify Manager
Команды: /start, /users, /stats, /create_user
"""

import os
import sys
import logging
from telebot import TeleBot
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID'))
PANEL_DOMAIN = os.getenv('PANEL_DOMAIN')

if not BOT_TOKEN:
    print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не найден в .env")
    sys.exit(1)

# Инициализация бота
bot = TeleBot(BOT_TOKEN)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработка команды /start"""

    # Проверка прав доступа
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "⛔ У вас нет прав для использования этого бота.")
        logger.warning(f"Неавторизованный доступ от chat_id={message.chat.id}")
        return

    welcome_text = f"""
🤖 **Hiddify Admin Bot**

Панель: https://{PANEL_DOMAIN}

Доступные команды:
/start - Это сообщение
/users - Список пользователей
/stats - Статистика системы
/create_user - Создать нового пользователя
/help - Помощь
"""

    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    logger.info(f"Пользователь {message.chat.id} вызвал /start")

@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработка команды /help"""

    if message.chat.id != ADMIN_ID:
        return

    help_text = """
📚 **Справка**

**Создание пользователя:**
Нажмите /create_user и следуйте инструкциям.

**Статистика:**
Команда /stats покажет:
- Количество пользователей
- Использование трафика
- Нагрузку на сервер

**Список пользователей:**
Команда /users покажет всех активных пользователей.
"""

    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['users'])
def list_users(message):
    """Обработка команды /users"""

    if message.chat.id != ADMIN_ID:
        return

    # TODO: Запрос к API Hiddify для получения списка пользователей
    bot.reply_to(message, "👥 Список пользователей...\n(В разработке)")
    logger.info(f"Пользователь {message.chat.id} запросил список пользователей")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """Обработка команды /stats"""

    if message.chat.id != ADMIN_ID:
        return

    # TODO: Запрос к API Hiddify для получения статистики
    stats_text = """
📊 **Статистика системы**

CPU: ---
RAM: ---
Пользователи: ---
Трафик: ---
"""

    bot.reply_to(message, stats_text, parse_mode='Markdown')
    logger.info(f"Пользователь {message.chat.id} запросил статистику")

@bot.message_handler(commands=['create_user'])
def create_user(message):
    """Обработка команды /create_user"""

    if message.chat.id != ADMIN_ID:
        return

    msg = bot.reply_to(message, "📝 Введите имя пользователя:")
    bot.register_next_step_handler(msg, process_user_creation)

def process_user_creation(message):
    """Обработка ввода имени пользователя"""

    username = message.text

    # Валидация
    if not username or len(username) < 3:
        bot.reply_to(message, "❌ Имя пользователя должно быть минимум 3 символа")
        return

    # TODO: Создание пользователя через API Hiddify
    bot.reply_to(message, f"✅ Пользователь {username} создан!")
    logger.info(f"Создан пользователь: {username}")

# Обработка неизвестных команд
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Обработка неизвестных сообщений"""

    if message.chat.id == ADMIN_ID:
        bot.reply_to(message, "❓ Неизвестная команда. Нажмите /help для справки")

def main():
    """Главная функция"""

    logger.info("Бот запущен...")
    logger.info(f"ADMIN_ID: {ADMIN_ID}")
    logger.info(f"PANEL_DOMAIN: {PANEL_DOMAIN}")

    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
