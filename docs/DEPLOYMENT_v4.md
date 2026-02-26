# Руководство по деплою Hiddify Bot v4.0

## Обзор

v4.0 включает значительные изменения в архитектуре:
- **PostgreSQL** вместо SQLite
- **Redis** для кэширования
- **Docker Compose** для контейнеризации
- **Stripe** для платежей
- **Prometheus + Grafana** для мониторинга

---

## Требования к серверу

### Минимальные характеристики
- CPU: 2 ядра
- RAM: 2 GB (рекомендуется 4 GB)
- Disk: 20 GB
- OS: Ubuntu 20.04+ / Debian 11+

### Программное обеспечение
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.9+

---

## План миграции

### Этап 1: Подготовка (на локальной машине)

```bash
# 1. Сделайте бэкап текущей БД
ssh kodu-3xui "sqlite3 /opt/hiddify-manager/data/bot.db '.dump' > backup.sql"

# 2. Клонируйте репозиторий и переключитесь на v4.0
git pull
git checkout main  # или соответствующую ветку

# 3. Проверьте новые зависимости
pip install -r requirements.txt
```

### Этап 2: Подготовка сервера

```bash
# 1. Запустите скрипт подготовки сервера
scp scripts/prepare-server-v4.sh kodu-3xui:/tmp/
ssh kodu-3xui "sudo bash /tmp/prepare-server-v4.sh"

# 2. Отредактируйте .env файл на сервере
ssh kodu-3xui "nano /opt/hiddify-manager/.env"

# Обязательно заполните:
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_ADMIN_ID
# - POSTGRES_PASSWORD (сгенерируйте новый пароль)
# - REDIS_PASSWORD (сгенерируйте новый пароль)
# - STRIPE_SECRET_KEY (если используете Stripe)
```

### Этап 3: Деплой Docker контейнеров

```bash
# 1. Скопируйте файлы на сервер
rsync -avz --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  scripts/ kodu-3xui:/opt/hiddify-manager/
rsync -avz infrastructure/ kodu-3xui:/opt/hiddify-manager/

# 2. Запустите контейнеры
ssh kodu-3xui << 'EOF'
cd /opt/hiddify-manager/infrastructure/docker

# Запуск PostgreSQL и Redis
docker-compose up -d postgres redis

# Ожидание готовности (10-20 секунд)
sleep 15

# Запуск бота
docker-compose up -d telegram-bot

# Запуск мониторинга (опционально)
docker-compose up -d prometheus grafana

# Проверка статуса
docker-compose ps
EOF
```

### Этап 4: Миграция данных (SQLite → PostgreSQL)

```bash
# 1. Запустите миграцию в dry-run режиме
ssh kodu-3xui << 'EOF'
cd /opt/hiddify-manager
python3 scripts/migrate_to_postgres.py --dry-run
EOF

# 2. Если dry-run прошёл успешно, выполните реальную миграцию
ssh kodu-3xui << 'EOF'
cd /opt/hiddify-manager
python3 scripts/migrate_to_postgres.py --migrate
EOF
```

### Этап 5: Проверка деплоя

```bash
# 1. Проверьте health endpoint
curl http://kodu-3xui:8080/health

# 2. Проверьте логи бота
ssh kodu-3xui "docker-compose -f /opt/hiddify-manager/infrastructure/docker/docker-compose.yml logs -f telegram-bot"

# 3. Протестируйте бота в Telegram
# - Нажмите /start
# - Проверьте новые команды (/support, /buy)
# - Проверьте Config Builder

# 4. Проверьте мониторинг
# Prometheus: http://kodu-3xui:9091
# Grafana: http://kodu-3xui:3000 (admin / пароль из .env)
```

---

## Rollback (возврат на v3.1.1)

Если что-то пошло не так:

```bash
ssh kodu-3xui << 'EOF'
cd /opt/hiddify-manager/infrastructure/docker

# Остановить контейнеры
docker-compose down

# Восстановить из бэкапа SQLite
cp backups/bot_backup_*.db ../data/bot.db

# Перезапустить сервис v3.1.1
systemctl restart hiddify-bot.service
EOF
```

---

## Мониторинг

### Prometheus метрики

Доступные метрики:
- `telegram_bot_messages_total` - Всего сообщений
- `telegram_bot_configs_generated_total` - Сгенерировано конфигов
- `telegram_bot_payments_completed_total` - Завершённых платежей
- `telegram_bot_active_users` - Активных пользователей

Эндпоинт: `http://server:9090/metrics`

### Grafana дашборды

1. Откройте Grafana: `http://server:3000`
2. Логин: `admin` / пароль из `.env`
3. Добавьте Prometheus datasource: `http://prometheus:9090`
4. Импортируйте дашборды из `infrastructure/docker/grafana/dashboards/`

---

## Troubleshooting

### Проблема: Бот не запускается

```bash
# Проверьте логи
docker-compose logs telegram-bot

# Проверьте переменные окружения
docker-compose exec telegram-bot env | grep TELEGRAM

# Проверьте подключение к БД
docker-compose exec postgres psql -U hiddify_user -d hiddify_bot
```

### Проблема: PostgreSQL не подключается

```bash
# Проверьте статус контейнера
docker-compose ps postgres

# Проверьте логи
docker-compose logs postgres

# Перезапустите контейнер
docker-compose restart postgres
```

### Проблема: Redis не подключается

```bash
# Проверьте статус
docker-compose ps redis

# Проверьте логи
docker-compose logs redis

# Проверьте подключение
docker-compose exec redis redis-cli ping
```

### Проблема: Stripe платежи не работают

```bash
# Проверьте переменные
docker-compose exec telegram-bot env | grep STRIPE

# Проверьте webhook endpoint
curl -X POST http://server:8080/webhook/stripe
```

---

## Полезные команды

### Docker Compose

```bash
# Статус контейнеров
docker-compose ps

# Логи всех контейнеров
docker-compose logs

# Логи конкретного контейнера
docker-compose logs -f telegram-bot

# Перезапуск контейнера
docker-compose restart telegram-bot

# Остановка всех контейнеров
docker-compose down

# Остановка с удалением volumes
docker-compose down -v
```

### PostgreSQL

```bash
# Подключиться к БД
docker-compose exec postgres psql -U hiddify_user -d hiddify_bot

# Сделать бэкап
docker-compose exec postgres pg_dump -U hiddify_user hiddify_bot > backup.sql

# Восстановить из бэкапа
cat backup.sql | docker-compose exec -T postgres psql -U hiddify_user -d hiddify_bot
```

### Redis

```bash
# Подключиться к Redis
docker-compose exec redis redis-cli

AUTH password_from_env

# Проверить ключи
KEYS *

# Получить значение
GET user:123:profile

# Очистить все (осторожно!)
FLUSHALL
```

---

## Безопасность

### Обязательные действия после деплоя:

1. **Изменить пароли по умолчанию**
   - PostgreSQL (`POSTGRES_PASSWORD` в .env)
   - Redis (`REDIS_PASSWORD` в .env)
   - Grafana (`GRAFANA_ADMIN_PASSWORD` в .env)

2. **Настроить firewall**
   ```bash
   ufw enable
   ufw allow 22/tcp  # SSH
   ufw allow 80/tcp  # HTTP
   ufw allow 443/tcp # HTTPS
   # Prometheus/Grafana только для доверенных IP
   ufw allow from YOUR_IP to any port 9091,3000
   ```

3. **Настроить SSL для Grafana** (если используется извне)
   - Используйте reverse proxy (nginx)
   - Let's Encrypt сертификаты

4. **Регулярные бэкапы**
   ```bash
   # Добавить в cron
   0 2 * * * docker-compose exec postgres pg_dump -U hiddify_user hiddify_bot > /backups/postgres_$(date +\%Y\%m\%d).sql
   ```

---

## Контакты

При проблемах с деплоем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте health endpoint: `curl http://localhost:8080/health`
3. Смотрите SESSION.md для истории изменений

---

**Дата**: 2026-02-27
**Версия**: 4.0.0
**Статус**: Production Ready
