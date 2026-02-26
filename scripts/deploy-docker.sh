#!/bin/bash
# Деплой с Docker Compose (v4.0)
#
# Новое в v4.0:
# - PostgreSQL вместо SQLite
# - Redis для кэширования
# - Prometheus + Grafana мониторинг
# - Stripe платежи
#
# Использование:
#   bash scripts/deploy-docker.sh [environment]
#
# Переменные окружения:
#   SSH_PRIVATE_KEY - путь к приватному SSH ключу
#   SERVER_HOST - хост сервера (kodu-3xui или IP)
#   SERVER_USER - пользователь SSH (root или другой)
#   DEPLOY_PATH - путь для деплоя (опционально)

set -e  # Остановить при ошибке
set -u  # Остановить при неопределённой переменной

# Конфигурация
SERVER_HOST="${SERVER_HOST:-5.45.114.73}"  # kodu-3xui
SERVER_USER="${SERVER_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/hiddify-manager}"

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

# Проверка переменных окружения
check_env_vars() {
    log_step "Проверка переменных окружения..."

    if [[ "$SERVER_HOST" == "your-server.com" ]] || [[ -z "$SERVER_HOST" ]]; then
        log_error "SERVER_HOST не установлен. Экспортируйте SERVER_HOST=your-host.com"
        exit 1
    fi

    log_info "Сервер: $SERVER_USER@$SERVER_HOST"
    log_info "Путь деплоя: $DEPLOY_PATH"
}

# Бэкап текущей БД
backup_database() {
    log_step "Создание бэкапа текущей БД..."

    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
        cd /opt/hiddify-manager

        # Бэкап SQLite если существует
        if [[ -f data/bot.db ]]; then
            BACKUP_NAME="bot_backup_$(date +%Y%m%d_%H%M%S).db"
            cp data/bot.db "backups/$BACKUP_NAME"
            echo "✅ SQLite бэкап создан: $BACKUP_NAME"

            # Удалить старые бэкапы (оставить 5 последних)
            ls -t backups/*.db 2>/dev/null | tail -n +6 | xargs -r rm
            echo "🗑️  Старые бэкапы удалены"
        fi

        # Бэкап PostgreSQL если запущен
        if docker ps | grep -q hiddify-postgres; then
            BACKUP_NAME="postgres_backup_$(date +%Y%m%d_%H%M%S).sql"
            docker exec hiddify-postgres pg_dump -U hiddify_user hiddify_bot > "backups/$BACKUP_NAME"
            echo "✅ PostgreSQL бэкап создан: $BACKUP_NAME"
        fi
EOF
}

# Установка Docker и Docker Compose
install_docker() {
    log_step "Проверка Docker..."

    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
        # Проверка Docker
        if ! command -v docker &> /dev/null; then
            echo "📦 Установка Docker..."
            curl -fsSL https://get.docker.com -o get-docker.sh
            sh get-docker.sh
            systemctl enable docker
            systemctl start docker
            echo "✅ Docker установлен"
        else
            echo "✅ Docker уже установлен: $(docker --version)"
        fi

        # Проверка Docker Compose
        if ! command -v docker-compose &> /dev/null; then
            echo "📦 Установка Docker Compose..."
            curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
            echo "✅ Docker Compose установлен"
        else
            echo "✅ Docker Compose уже установлен: $(docker-compose --version)"
        fi
EOF
}

# Подготовка файлов для деплоя
prepare_deploy() {
    log_step "Подготовка файлов для деплоя..."

    # Проверить наличие .env файла
    if [[ ! -f .env ]]; then
        log_error ".env файл не найден. Создайте .env файл с настройками."
        exit 1
    fi

    # Создать необходимые директории на сервере
    ssh ${SERVER_USER}@${SERVER_HOST} << EOF
        mkdir -p $DEPLOY_PATH/{scripts,infrastructure,data,logs,backups}
        mkdir -p $DEPLOY_PATH/infrastructure/docker/grafana/{datasources,dashboards}
    EOF
}

# Копирование файлов на сервер
copy_files() {
    log_step "Копирование файлов на сервер..."

    # Копировать скрипты
    rsync -avz --exclude='__pycache__' \
              --exclude='*.pyc' \
              --exclude='.pytest_cache' \
              scripts/ ${SERVER_USER}@${SERVER_HOST}:$DEPLOY_PATH/scripts/

    # Копировать Docker инфраструктуру
    rsync -avz infrastructure/docker/ ${SERVER_USER}@${SERVER_HOST}:$DEPLOY_PATH/infrastructure/docker/

    # Копировать requirements
    rsync -avz requirements.txt ${SERVER_USER}@${SERVER_HOST}:$DEPLOY_PATH/

    # Копировать .env (только если не существует на сервере)
    ssh ${SERVER_USER}@${SERVER_HOST} << EOF
        if [[ ! -f $DEPLOY_PATH/.env ]]; then
            echo "⚠️  .env не найден на сервере"
        fi
EOF
}

# Запуск контейнеров
start_containers() {
    log_step "Запуск контейнеров..."

    ssh ${SERVER_USER}@${SERVER_HOST} << EOF
        cd $DEPLOY_PATH/infrastructure/docker

        # Остановить старые контейнеры
        docker-compose down 2>/dev/null || true

        # Запустить PostgreSQL и Redis
        echo "🚀 Запуск PostgreSQL и Redis..."
        docker-compose up -d postgres redis

        # Ожидание готовности БД
        echo "⏳ Ожидание готовности PostgreSQL..."
        sleep 10

        # Запуск бота
        echo "🚀 Запуск бота..."
        docker-compose up -d telegram-bot

        # Запуск мониторинга
        echo "🚀 Запуск Prometheus и Grafana..."
        docker-compose up -d prometheus grafana

        # Показать статус
        echo ""
        echo "📊 Статус контейнеров:"
        docker-compose ps
EOF
}

# Проверка здоровья
health_check() {
    log_step "Проверка здоровья..."

    # Проверка health endpoint
    sleep 5

    if curl -sf http://${SERVER_HOST}:8080/health > /dev/null 2>&1; then
        log_info "✅ Health check пройден"
    else
        log_warn "⚠️  Health endpoint недоступен (это нормально для первого запуска)"
    fi

    # Проверка Prometheus
    if curl -sf http://${SERVER_HOST}:9091/-/healthy > /dev/null 2>&1; then
        log_info "✅ Prometheus доступен: http://${SERVER_HOST}:9091"
    fi

    # Проверка Grafana
    if curl -sf http://${SERVER_HOST}:3000/api/health > /dev/null 2>&1; then
        log_info "✅ Grafana доступна: http://${SERVER_HOST}:3000"
        log_info "   Логин: admin / пароль из .env (GRAFANA_ADMIN_PASSWORD)"
    fi
}

# Показать информацию
show_info() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "🎉 Деплой завершён!"
    echo "═══════════════════════════════════════════════════"
    echo ""
    echo "📊 Доступные сервисы:"
    echo "   • Telegram Bot: работает в контейнере"
    echo "   • Health Check:  http://${SERVER_HOST}:8080/health"
    echo "   • Prometheus:    http://${SERVER_HOST}:9091"
    echo "   • Grafana:       http://${SERVER_HOST}:3000"
    echo ""
    echo "📝 Полезные команды:"
    echo "   ssh ${SERVER_USER}@${SERVER_HOST}"
    echo "   cd $DEPLOY_PATH/infrastructure/docker"
    echo "   docker-compose logs -f telegram-bot"
    echo "   docker-compose ps"
    echo "   docker-compose restart telegram-bot"
    echo ""
}

# Главная функция
main() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "🚀 Hiddify Bot v4.0 Deployment (Docker)"
    echo "═══════════════════════════════════════════════════"
    echo ""

    check_env_vars
    backup_database
    install_docker
    prepare_deploy
    copy_files
    start_containers
    health_check
    show_info
}

# Запуск
main "$@"
