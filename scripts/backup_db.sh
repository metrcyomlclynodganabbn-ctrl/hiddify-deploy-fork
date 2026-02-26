#!/bin/bash
#
# Hiddify Manager - Database Backup Script
# Version: 2.1.1
#
# Создаёт бэкапы SQLite базы данных каждые 6 часов
# Хранит только последние 7 бэкапов для экономии места
#
# Использование: добавьте в crontab:
# 0 */6 * * * /opt/hiddify-manager/scripts/backup_db.sh

set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

# Путь к директории проекта (автоопределение)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Путь к БД (можно переопределить через переменную окружения)
DB_PATH="${DB_PATH:-/opt/hiddify-manager/data/bot.db}"

# Директория для бэкапов
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Лог-файл
LOG_FILE="${PROJECT_ROOT}/logs/backup.log"

# Количество хранимых бэкапов
KEEP_BACKUPS=7

# ═══════════════════════════════════════════════════════════════
# ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

create_backup() {
    local date_suffix=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/bot_${date_suffix}.db"

    # Создать директорию для бэкапов
    mkdir -p "$BACKUP_DIR"

    # Создать директорию для логов
    mkdir -p "$(dirname "$LOG_FILE")"

    log "INFO" "Начало бэкапа БД"
    log "INFO" "Исходная БД: ${DB_PATH}"
    log "INFO" "Бэкап: ${backup_file}"

    # Проверить существование БД
    if [[ ! -f "$DB_PATH" ]]; then
        log "ERROR" "База данных не найдена: ${DB_PATH}"
        return 1
    fi

    # Создать бэкап используя SQLite команду .backup
    if sqlite3 "$DB_PATH" ".backup '${backup_file}'"; then
        log "INFO" "Бэкап создан успешно"

        # Проверить размер бэкапа
        local backup_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
        local db_size=$(stat -f%z "$DB_PATH" 2>/dev/null || stat -c%s "$DB_PATH" 2>/dev/null || echo "0")

        log "INFO" "Размер исходной БД: ${db_size} bytes"
        log "INFO" "Размер бэкапа: ${backup_size} bytes"

        # Проверить что бэкап не пустой
        if [[ "$backup_size" -lt 1000 ]]; then
            log "ERROR" "Бэкап слишком маленький (${backup_size} bytes), возможно повреждён"
            rm -f "$backup_file"
            return 1
        fi
    else
        log "ERROR" "Ошибка при создании бэкапа"
        return 1
    fi

    # Сделать бэкап доступным только для владельца
    chmod 600 "$backup_file"

    return 0
}

cleanup_old_backups() {
    log "INFO" "Очистка старых бэкапов (хранить последние ${KEEP_BACKUPS})"

    # Посчитать количество бэкапов
    local backup_count=$(ls -1 "${BACKUP_DIR}"/bot_*.db 2>/dev/null | wc -l | tr -d ' ')

    if [[ "$backup_count" -gt "$KEEP_BACKUPS" ]]; then
        local delete_count=$((backup_count - KEEP_BACKUPS))
        log "INFO" "Найдено ${backup_count} бэкапов, удаление ${delete_count} старых"

        # Удалить старые бэкапы
        ls -t "${BACKUP_DIR}"/bot_*.db | tail -n +$((KEEP_BACKUPS + 1)) | while read -r old_backup; do
            log "INFO" "Удаление: $(basename "$old_backup")"
            rm -f "$old_backup"
        done
    else
        log "INFO" "Количество бэкапов в норме: ${backup_count}"
    fi
}

show_summary() {
    log "INFO" "────────────────────────────────────────────"
    log "INFO" "Текущие бэкапы:"

    # Показать список бэкапов с размерами
    ls -lh "${BACKUP_DIR}"/bot_*.db 2>/dev/null | tail -r | while read -r line; do
        log "INFO" "$line"
    done

    # Общий размер бэкапов
    local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log "INFO" "Общий размер бэкапов: ${total_size}"
    log "INFO" "────────────────────────────────────────────"
}

# ═══════════════════════════════════════════════════════════════
# ОСНОВНОЙ БЛОК
# ═══════════════════════════════════════════════════════════════

log "INFO" "═══════════════════════════════════════════════════"
log "INFO" "Запуск скрипта бэкапа БД"

# Выполнить бэкап
if create_backup; then
    # Очистить старые бэкапы
    cleanup_old_backups

    # Показать сводку
    show_summary

    log "INFO" "Бэкап завершён успешно"
    exit 0
else
    log "ERROR" "Бэкап завершён с ошибками"
    exit 1
fi
