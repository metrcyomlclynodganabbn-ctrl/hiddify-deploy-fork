#!/bin/bash
# Установка systemd service для Hiddify Bot
#
# Использование:
#   bash scripts/install_service.sh [server_host]
#
# Пример:
#   bash scripts/install_service.sh 144.31.192.47

set -e

SERVER_HOST="${1:-}"
SERVER_USER="${SERVER_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/hiddify-manager}"

if [[ -z "$SERVER_HOST" ]]; then
    echo "❌ Укажите хост сервера"
    echo "Использование: bash $0 <server_host>"
    exit 1
fi

echo "🚀 Установка hiddify-bot.service на $SERVER_HOST..."

# Проверка соединения
echo "📡 Проверка соединения..."
ssh -o ConnectTimeout=5 ${SERVER_USER}@${SERVER_HOST} "echo 'Соединение установлено'" || {
    echo "❌ Не удалось подключиться к серверу"
    exit 1
}

# Копирование service файла
echo "📄 Копирование systemd unit файла..."
scp systemd/hiddify-bot.service ${SERVER_USER}@${SERVER_HOST}:/tmp/

# Установка на сервере
ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
set -e

# Создать директорию если не существует
mkdir -p /opt/hiddify-manager/{data,logs,scripts}

# Установить service файл
mv /tmp/hiddify-bot.service /etc/systemd/system/

# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable hiddify-bot

echo "✅ Service файл установлен"
EOF

echo "✅ Установка завершена!"
echo ""
echo "Для запуска бота:"
echo "  ssh ${SERVER_USER}@${SERVER_HOST} 'systemctl start hiddify-bot'"
echo ""
echo "Для просмотра логов:"
echo "  ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u hiddify-bot -f'"
