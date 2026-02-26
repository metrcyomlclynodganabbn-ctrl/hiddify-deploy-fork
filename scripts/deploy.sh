#!/bin/bash
# Автоматический деплой на сервер
#
# Использование:
#   bash scripts/deploy.sh [environment]
#
# Параметры окружения:
#   SSH_PRIVATE_KEY - путь к приватному SSH ключу
#   SERVER_HOST - хост сервера
#   SERVER_USER - пользователь SSH
#   DEPLOY_PATH - путь для деплоя (опционально)

set -e  # Остановить при ошибке
set -u  # Остановить при неопределённой переменной

# Конфигурация
SERVER_HOST="${SERVER_HOST:-your-server.com}"
SERVER_USER="${SERVER_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/hiddify-manager}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Проверка переменных окружения
check_env_vars() {
    log_info "Проверка переменных окружения..."

    if [[ -z "${SSH_PRIVATE_KEY:-}" ]] && [[ -z "${SSH_KEY_FILE:-}" ]]; then
        log_warn "SSH_PRIVATE_KEY или SSH_KEY_FILE не установлены, использую ~/.ssh/id_rsa"
    fi

    if [[ "$SERVER_HOST" == "your-server.com" ]]; then
        log_error "SERVER_HOST не установлен. Экспортируйте SERVER_HOST=your-host.com"
        exit 1
    fi

    log_info "Переменные окружения OK"
}

# Подготовка к деплою
prepare_deploy() {
    log_info "Подготовка к деплою..."

    # Проверить наличие .env файла
    if [[ ! -f .env ]]; then
        log_error ".env файл не найден. Создайте .env файл с настройками."
        exit 1
    fi

    # Создать временную директорию для деплоя
    TMP_DIR=$(mktemp -d)
    log_info "Временная директория: $TMP_DIR"

    # Копировать файлы проекта
    rsync -av --exclude='.git' \
              --exclude='__pycache__' \
              --exclude='*.pyc' \
              --exclude='.venv' \
              --exclude='venv' \
              --exclude='node_modules' \
              --exclude='.pytest_cache' \
              --exclude='htmlcov' \
              --exclude='.coverage' \
              scripts/ "$TMP_DIR/scripts/"

    # Копировать configs
    if [[ -d configs ]]; then
        rsync -av configs/ "$TMP_DIR/configs/"
    fi

    # Копировать .env.example (не .env - секреты!)
    if [[ -f .env.example ]]; then
        cp .env.example "$TMP_DIR/"
    fi

    echo "$TMP_DIR"
}

# Деплой на сервер
deploy_to_server() {
    local TMP_DIR=$1

    log_info "Деплой на сервер $SERVER_HOST..."

    # Определить SSH команду
    if [[ -n "${SSH_KEY_FILE:-}" ]]; then
        SSH_CMD="ssh -i $SSH_KEY_FILE"
        SCP_CMD="scp -i $SSH_KEY_FILE"
        RSYNC_CMD="rsync -avz -e 'ssh -i $SSH_KEY_FILE'"
    elif [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
        # Использовать временный файл для ключа
        KEY_FILE=$(mktemp)
        echo "$SSH_PRIVATE_KEY" > "$KEY_FILE"
        chmod 600 "$KEY_FILE"
        SSH_CMD="ssh -i $KEY_FILE"
        SCP_CMD="scp -i $KEY_FILE"
        RSYNC_CMD="rsync -avz -e 'ssh -i $KEY_FILE'"
    else
        SSH_CMD="ssh"
        SCP_CMD="scp"
        RSYNC_CMD="rsync -avz"
    fi

    # Создать директорию на сервере
    $SSH_CMD ${SERVER_USER}@${SERVER_HOST} "mkdir -p $DEPLOY_PATH/scripts"

    # Копировать файлы
    log_info "Копирование файлов..."
    $RSYNC_CMD "$TMP_DIR/" ${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}/

    # Перезапустить бота
    log_info "Перезапуск бота..."
    $SSH_CMD ${SERVER_USER}@${SERVER_HOST} << EOF
        cd $DEPLOY_PATH

        # Проверить наличие .env
        if [[ ! -f .env ]]; then
            echo ".env файл не найден, копирую из .env.example"
            cp .env.example .env
            echo "⚠️  Отредактируйте .env файл с реальными значениями!"
        fi

        # Установить зависимости если нужно
        if [[ -f requirements.txt ]]; then
            pip3 install -r requirements.txt --quiet
        fi

        # Перезапустить systemd service если существует
        if systemctl is-active --quiet hiddify-bot; then
            systemctl restart hiddify-bot
            echo "✅ Сервис hiddify-bot перезапущен"
        else
            echo "ℹ️  Сервис hiddify-bot не найден, запускаю вручную..."
            # Остановить старый процесс если есть
            pkill -f "python3.*monitor_bot.py" || true
            # Запустить в фоне
            nohup python3 scripts/monitor_bot.py > logs/bot.log 2>&1 &
            echo "✅ Бот запущен в фоне"
        fi
EOF

    log_info "Деплой завершён"

    # Очистка
    if [[ -n "${KEY_FILE:-}" ]]; then
        rm -f "$KEY_FILE"
    fi
    rm -rf "$TMP_DIR"
}

# Запуск health check
run_health_check() {
    log_info "Запуск health check..."

    if [[ -n "${SSH_KEY_FILE:-}" ]]; then
        SSH_CMD="ssh -i $SSH_KEY_FILE"
    elif [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
        KEY_FILE=$(mktemp)
        echo "$SSH_PRIVATE_KEY" > "$KEY_FILE"
        chmod 600 "$KEY_FILE"
        SSH_CMD="ssh -i $KEY_FILE"
    else
        SSH_CMD="ssh"
    fi

    $SSH_CMD ${SERVER_USER}@${SERVER_HOST} << EOF
        cd $DEPLOY_PATH
        python3 scripts/health_check.py
EOF

    if [[ $? -eq 0 ]]; then
        log_info "✅ Health check пройден"
    else
        log_error "❌ Health check не пройден"
    fi

    if [[ -n "${KEY_FILE:-}" ]]; then
        rm -f "$KEY_FILE"
    fi
}

# Главная функция
main() {
    log_info "Начало деплоя..."

    check_env_vars

    TMP_DIR=$(prepare_deploy)

    deploy_to_server "$TMP_DIR"

    run_health_check

    log_info "✅ Деплой успешно завершён!"
}

# Запуск
main "$@"
