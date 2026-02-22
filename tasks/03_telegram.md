# ЭТАП 3: Настройка Telegram-бота админки

## Цель
Настроить интеграцию с Telegram для управления панелью через бота.

## Шаги

### 1. Проверка бота
```bash
# Проверка токена
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" | jq

# Ожидаемый вывод:
# {
#   "ok": true,
#   "result": {
#     "id": 123456789,
#     "is_bot": true,
#     "first_name": "YourBotName",
#     ...
#   }
# }
```

### 2. Установка зависимостей Python
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Создание виртуального окружения
python3 -m venv /opt/hiddify-manager/venv

# Активация и установка пакетов
source /opt/hiddify-manager/venv/bin/activate
pip install --upgrade pip
pip install pyTelegramBotAPI==4.22.0
pip install requests
pip install python-dotenv

echo "✅ Зависимости Python установлены"
EOF
```

### 3. Настройка интеграции в панели Hiddify
```bash
# Через API или веб-интерфейс панели
curl -X POST "https://$PANEL_DOMAIN/api/admin/settings" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_bot_token": "'"$TELEGRAM_BOT_TOKEN"'",
    "telegram_admin_id": '"$TELEGRAM_ADMIN_ID"',
    "telegram_proxy_enabled": '"$TELEGRAM_PROXY_ENABLED"'
  }'
```

### 4. Создание скрипта бота
```bash
# Создание монитора бота
cat > scripts/monitor_bot.py <<'BOT_SCRIPT'
#!/usr/bin/env python3
"""
Telegram Bot Monitor для Hiddify Manager
Команды: /start, /users, /stats, /create_user
"""

import os
import logging
from telebot import TeleBot
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID'))

# Инициализация бота
bot = TeleBot(BOT_TOKEN)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "⛔ У вас нет прав для использования этого бота.")
        return

    welcome_text = """
🤖 **Hiddify Admin Bot**

Доступные команды:
/start - Это сообщение
/users - Список пользователей
/stats - Статистика системы
/create_user - Создать нового пользователя
/help - Помощь
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id != ADMIN_ID:
        return

    # TODO: Запрос к API Hiddify для получения списка пользователей
    bot.reply_to(message, "👥 Список пользователей...\n(В разработке)")

@bot.message_handler(commands=['stats'])
def show_stats(message):
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

@bot.message_handler(commands=['create_user'])
def create_user(message):
    if message.chat.id != ADMIN_ID:
        return

    msg = bot.reply_to(message, "📝 Введите имя пользователя:")
    bot.register_next_step_handler(msg, process_user_creation)

def process_user_creation(message):
    username = message.text
    # TODO: Создание пользователя через API Hiddify
    bot.reply_to(message, f"✅ Пользователь {username} создан!")

if __name__ == '__main__':
    logging.info("Бот запущен...")
    bot.infinity_polling()
BOT_SCRIPT

chmod +x scripts/monitor_bot.py
```

### 5. Настройка systemd службы для бота
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Создание systemd unit
cat > /etc/systemd/system/hiddify-bot.service <<'SERVICE'
[Unit]
Description=Hiddify Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/hiddify-manager
Environment="PATH=/opt/hiddify-manager/venv/bin"
ExecStart=/opt/hiddify-manager/venv/bin/python /opt/hiddify-manager/scripts/monitor_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# Перезагрузка systemd и запуск службы
systemctl daemon-reload
systemctl enable hiddify-bot
systemctl start hiddify-bot

# Проверка статуса
systemctl status hiddify-bot --no-pager

echo "✅ Telegram-бот установлен как служба"
EOF
```

### 6. Тестирование бота
```bash
# Отправка тестового сообщения
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -d "chat_id=$TELEGRAM_ADMIN_ID" \
  -d "text=✅ Бот успешно настроен! Попробуйте команду /start"

# Проверка логов
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "journalctl -u hiddify-bot -n 50 --no-pager"
```

## Критерии завершения
- ✅ Бот отвечает на `/start`
- ✅ Команды `/users`, `/stats` работают
- ✅ Бот запущен как systemd служба
- ✅ Админ получает уведомления

## Troubleshooting

### Если бот не отвечает
```bash
# Проверить токен
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"

# Проверить логи
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "journalctl -u hiddify-bot -f"

# Перезапустить бота
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "systemctl restart hiddify-bot"
```

### Если @BotFather блокирует команды
```bash
# Отключить privacy mode
# Отправить /setprivacy в @BotFather
# Вырать бота → "Disable"
```

## Логирование
```bash
exec > >(tee -a logs/telegram.log)
exec 2>&1
```
