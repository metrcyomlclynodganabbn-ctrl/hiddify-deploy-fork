#!/bin/bash
# Подготовка сервера к деплою v4.0 (Docker + PostgreSQL + Redis)
#
# Этот скрипт устанавливает необходимые компоненты на сервере
# и готовит его к деплою через Docker Compose

set -e  # Остановить при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Проверка прав root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Этот скрипт должен быть запущен с root правами"
        log_info "Используйте: sudo bash $0"
        exit 1
    fi
}

# Обновление системы
update_system() {
    log_step "Обновление системы..."

    apt-get update -qq
    apt-get upgrade -y -qq

    log_info "✅ Система обновлена"
}

# Установка Docker
install_docker() {
    log_step "Установка Docker..."

    if command -v docker &> /dev/null; then
        log_info "Docker уже установлен: $(docker --version)"
    else
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        systemctl enable docker
        systemctl start docker
        rm get-docker.sh
        log_info "✅ Docker установлен"
    fi
}

# Установка Docker Compose
install_docker_compose() {
    log_step "Установка Docker Compose..."

    if command -v docker-compose &> /dev/null; then
        log_info "Docker Compose уже установлен: $(docker-compose --version)"
    else
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        log_info "✅ Docker Compose установлен"
    fi
}

# Установка Python и pip
install_python() {
    log_step "Установка Python и pip..."

    apt-get install -y python3 python3-pip python3-venv

    log_info "✅ Python установлен: $(python3 --version)"
}

# Создание пользователя hiddify
create_hiddify_user() {
    log_step "Создание пользователя hiddify..."

    if id "hiddify" &>/dev/null; then
        log_info "Пользователь hiddify уже существует"
    else
        useradd -r -s /bin/bash -d /opt/hiddify-manager hiddify
        log_info "✅ Пользователь hiddify создан"
    fi
}

# Создание директорий
create_directories() {
    log_step "Создание директорий..."

    mkdir -p /opt/hiddify-manager/{scripts,infrastructure,data,logs,backups}
    mkdir -p /opt/hiddify-manager/infrastructure/docker/grafana/{datasources,dashboards}

    chown -R hiddify:hiddify /opt/hiddify-manager

    log_info "✅ Директории созданы"
}

# Установка зависимостей Python
install_python_dependencies() {
    log_step "Установка зависимостей Python..."

    if [[ -f /opt/hiddify-manager/requirements.txt ]]; then
        su - hiddify -c "cd /opt/hiddify-manager && pip3 install --user -r requirements.txt"
        log_info "✅ Зависимости Python установлены"
    else
        log_warn "requirements.txt не найден, пропускаю"
    fi
}

# Создание .env файла
create_env_file() {
    log_step "Создание .env файла..."

    ENV_FILE="/opt/hiddify-manager/.env"

    if [[ -f "$ENV_FILE" ]]; then
        log_warn ".env файл уже существует, пропускаю"
        return
    fi

    cat > "$ENV_FILE" << 'EOF'
# === TELEGRAM BOT ===
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_ID=your_admin_id_here
TELEGRAM_BOT_USERNAME=SKRTvpnbot

# === DATABASE (PostgreSQL) ===
DATABASE_URL=postgresql://hiddify_user:CHANGE_ME_PASSWORD@localhost:5432/hiddify_bot
POSTGRES_DB=hiddify_bot
POSTGRES_USER=hiddify_user
POSTGRES_PASSWORD=CHANGE_ME_PASSWORD
POSTGRES_PORT=5432

# === SQLite (резервный) ===
DB_PATH=/opt/hiddify-manager/data/bot.db

# === CACHE (Redis) ===
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=CHANGE_ME_PASSWORD
REDIS_PORT=6379

# === HIDDIFY MANAGER API ===
PANEL_DOMAIN=your-panel.example.com
HIDDIFY_API_TOKEN=your_api_token_here

# === VLESS REALITY CONFIG ===
VPS_IP=your_server_ip
REALITY_PUBLIC_KEY=your_public_key_here
REALITY_SNI=www.apple.com
REALITY_FINGERPRINT=chrome

# === PAYMENT SYSTEM (Stripe) ===
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here

# === MONITORING ===
METRICS_PORT=9090
HEALTH_PORT=8080
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=CHANGE_ME_PASSWORD
PROMETHEUS_PORT=9091
GRAFANA_PORT=3000

# === LOGGING ===
LOG_LEVEL=INFO
LOG_FILE=/opt/hiddify-manager/logs/bot.log
EOF

    chown hiddify:hiddify "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    log_info "✅ .env файл создан"
    log_warn "⚠️  Отредактируйте .env файл с реальными значениями!"
}

# Настройка firewall
setup_firewall() {
    log_step "Настройка firewall..."

    # Проверка наличия ufw
    if command -v ufw &> /dev/null; then
        # Разрешить необходимые порты
        ufw allow 22/tcp    # SSH
        ufw allow 80/tcp    # HTTP
        ufw allow 443/tcp   # HTTPS
        ufw allow 8080/tcp  # Health check
        ufw allow 9090/tcp  # Metrics (опционально)
        ufw allow 9091/tcp  # Prometheus (опционально)
        ufw allow 3000/tcp  # Grafana (опционально, только для доверенных IP)

        log_info "✅ Firewall настроен"
    else
        log_warn "ufw не найден, пропускаю настройку firewall"
    fi
}

# Создание systemd service (опционально, для fallback)
create_systemd_service() {
    log_step "Создание systemd service..."

    cat > /etc/systemd/system/hiddify-bot.service << 'EOF'
[Unit]
Description=Hiddify VPN Bot v4.0 with PostgreSQL and Redis
Documentation=https://github.com/hiddify/hiddify-manager
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=hiddify
Group=hiddify
WorkingDirectory=/opt/hiddify-manager

# Environment
EnvironmentFile=-/opt/hiddify-manager/.env

# ExecStart (для Docker Compose)
ExecStart=/usr/local/bin/docker-compose -f /opt/hiddify-manager/infrastructure/docker/docker-compose.yml up
ExecStop=/usr/local/bin/docker-compose -f /opt/hiddify-manager/infrastructure/docker/docker-compose.yml down

# Restart policy
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    log_info "✅ Systemd service создан"
}

# Показать информацию для завершения
show_completion_info() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo -e "${GREEN}🎉 Сервер готов к деплою v4.0!${NC}"
    echo "═══════════════════════════════════════════════════"
    echo ""
    echo "📝 Следующие шаги:"
    echo ""
    echo "1. Отредактируйте .env файл:"
    echo "   nano /opt/hiddify-manager/.env"
    echo ""
    echo "2. Разверните проект:"
    echo "   cd /opt/hiddify-manager/infrastructure/docker"
    echo "   docker-compose up -d"
    echo ""
    echo "3. Проверьте статус:"
    echo "   docker-compose ps"
    echo "   docker-compose logs -f telegram-bot"
    echo ""
    echo "4. Проверьте health endpoint:"
    echo "   curl http://localhost:8080/health"
    echo ""
    echo "5. Доступные сервисы:"
    echo "   • Health Check:  http://$(hostname -I | awk '{print $1}'):8080/health"
    echo "   • Prometheus:    http://$(hostname -I | awk '{print $1}'):9091"
    echo "   • Grafana:       http://$(hostname -I | awk '{print $1}'):3000"
    echo ""
    echo "═══════════════════════════════════════════════════"
}

# Главная функция
main() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "🚀 Подготовка сервера к деплою Hiddify Bot v4.0"
    echo "═══════════════════════════════════════════════════"
    echo ""

    check_root
    update_system
    install_docker
    install_docker_compose
    install_python
    create_hiddify_user
    create_directories
    create_env_file
    setup_firewall
    create_systemd_service
    show_completion_info
}

# Запуск
main "$@"
