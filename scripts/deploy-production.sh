#!/bin/bash
# Финальный деплой на продакшен сервер
#
# Полностью автоматизированный деплой v4.0 с миграцией данных

set -e  # Остановить при ошибке

# Конфигурация
SERVER_HOST="${SERVER_HOST:-5.45.114.73}"
SERVER_USER="${SERVER_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/hiddify-manager}"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# SSH команда с логированием
ssh_exec() {
    ssh ${SERVER_USER}@${SERVER_HOST} "$@"
}

echo ""
echo "═══════════════════════════════════════════════════"
echo "🚀 Финальный деплой Hiddify Bot v4.0"
echo "═══════════════════════════════════════════════════"
echo ""

# 1. Создание бэкапа
log_info "📦 Создание бэкапа данных..."
ssh_exec << 'EOF'
cd /opt/hiddify-manager
mkdir -p backups
BACKUP_NAME="bot_backup_$(date +%Y%m%d_%H%M%S).db"
if [[ -f data/bot.db ]]; then
    cp data/bot.db "backups/$BACKUP_NAME"
    echo "✅ SQLite бэкап: $BACKUP_NAME"
    ls -lh backups/$BACKUP_NAME
fi
EOF

# 2. Остановка бэкапа
log_info "💾 Сохранение бэкапа локально..."
scp kodu-3xui:/opt/hiddify-manager/backups/*.db ./backups/ 2>/dev/null || log_warn "Локальное сохранение бэкапа пропущено"

# 3. Деплой файлов
log_info "📤 Деплой файлов на сервер..."
rsync -avz --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.venv' \
  scripts/ kodu-3xui:${DEPLOY_PATH}/
rsync -avz infrastructure/ kodu-3xui:${DEPLOY_PATH}/
rsync -avz requirements.txt kodu-3xui:${DEPLOY_PATH}/

# 4. Запуск Docker контейнеров
log_info "🐳 Запуск Docker контейнеров..."
ssh_exec << 'EOF'
cd /opt/hiddify-manager/infrastructure/docker

# Остановить старые контейнеры
docker-compose down 2>/dev/null || true

# Запустить в правильном порядке
docker-compose up -d postgres redis
sleep 10

# Запустить бота
docker-compose up -d telegram-bot

# Запуск мониторинга
docker-compose up -d prometheus grafana

echo ""
echo "📊 Статус контейнеров:"
docker-compose ps
EOF

# 5. Проверка здоровья
sleep 5
log_info "🏥 Проверка здоровья..."

if curl -sf http://${SERVER_HOST}:8080/health > /dev/null 2>&1; then
    log_info "✅ Health check OK"
else
    log_warn "⚠️  Health check failed (возможно при первом запуске)"
fi

# 6. Показать информацию
echo ""
echo "═══════════════════════════════════════════════════"
echo "🎉 Деплой завершён!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "📊 Полезные команды:"
echo "   ssh kodu-3xui"
echo "   cd /opt/hiddify-manager/infrastructure/docker"
echo "   docker-compose logs -f telegram-bot"
echo ""
echo "🌐 Доступные сервисы:"
echo "   • Health:  http://${SERVER_HOST}:8080/health"
echo "   • Metrics: http://${SERVER_HOST}:9090"
echo "   • Prometheus: http://${SERVER_HOST}:9091"
echo "   • Grafana:  http://${SERVER_HOST}:3000"
echo ""
echo "📝 Bot: @SKRTvpnbot"
echo "═══════════════════════════════════════════════════"
