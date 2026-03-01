# Local Development Guide

## 🚀 Как запустить локально для тестов

### 1. Установка зависимостей

```bash
# Убедитесь, что вы в корне проекта
cd ~/workspace/hiddify-deploy-fork

# Создайте виртуальное окружение (если ещё нет)
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
# Скопируйте шаблон
cp .env.example .env

# Отредактируйте .env (минимальные настройки):
cat > .env << 'EOF'
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here
BOT_USERNAME=SKRTvpnbot
ADMIN_IDS=[123456789]  # Ваш Telegram ID

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hiddify_bot
POSTGRES_USER=hiddify_user
POSTGRES_PASSWORD=your_password_here

# Hiddify API
PANEL_DOMAIN=panel.yourvpn.ru
HIDDIFY_API_TOKEN=your_hiddify_api_token

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# CryptoBot (опционально)
CRYPTOBOT_API_TOKEN=your_cryptobot_token

# Security
SECRET_KEY=your-secret-key-here
EOF
```

### 3. Запуск PostgreSQL (Docker)

```bash
# Запустите PostgreSQL в Docker
docker run -d \
  --name hiddify-postgres \
  -e POSTGRES_DB=hiddify_bot \
  -e POSTGRES_USER=hiddify_user \
  -e POSTGRES_PASSWORD=your_password_here \
  -p 5432:5432 \
  -v hiddify-postgres-data:/var/lib/postgresql/data \
  postgres:15-alpine
```

### 4. Запуск Redis (Docker)

```bash
# Запустите Redis в Docker
docker run -d \
  --name hiddify-redis \
  -p 6379:6379 \
  -v hiddify-redis-data:/data \
  redis:7-alpine \
  redis-server --requirepass your_redis_password
```

### 5. Инициализация базы данных

```bash
# Инициализируйте таблицы
python -c "
from database.base import init_db
import asyncio

async def init():
    await init_db()
    print('✅ Database initialized!')

asyncio.run(init())
"
```

### 6. Миграция данных (если есть SQLite)

```bash
# Если у вас есть старая база SQLite
# Скопируйте её в data/bot.db

# Запустите миграцию
python scripts/migrate_sqlite_to_postgres.py
```

### 7. Запуск бота

```bash
# Запустите Aiogram 3 бот
python -m bot.main
```

Бот начнёт работать и будет слушать Telegram. Webhook сервер запустится на порту 8081.

---

## 🧪 Запуск тестов

### Unit тесты

```bash
# Запуск всех unit тестов
pytest tests/unit/ -v

# Запуск конкретного теста
pytest tests/unit/test_handlers.py::TestStartHandler::test_start_basic -v

# Запуск с покрытием
pytest tests/unit/ -v --cov=bot --cov=database --cov-report=html
```

---

## 🐳 Запуск через Docker Compose (полный стэк)

```bash
# Перейдите в docker директорию
cd infrastructure/docker

# Запустите все сервисы
docker-compose up -d

# Проверьте статус
docker-compose ps

# Логи бота
docker-compose logs -f telegram-bot
```

Доступные порты:
- **9090** - Prometheus metrics
- **9091** - Prometheus UI
- **3000** - Grafana
- **8080** - Health check
- **8081** - Webhook server (CryptoBot)

---

## 🔄 Обновление кода в Docker

```bash
# Пересобрать бота после изменений
docker-compose up -d --build telegram-bot

# Перезапустить бота
docker-compose restart telegram-bot
```

---

## 📊 Мониторинг

### Prometheus Metrics

```bash
# Метрики бота
curl http://localhost:9090/metrics

# Health check
curl http://localhost:8080/health

# Webhook health
curl http://localhost:8081/health
```

### Grafana Dashboard

1. Откройте http://localhost:3000
2. Логин: `admin` / пароль из `.env` (GRAFANA_ADMIN_PASSWORD)

---

## 🐛 Troubleshooting

### Бот не запускается

```bash
# Проверьте логи
docker-compose logs telegram-bot

# Проверьте статус сервисов
docker-compose ps

# Перезапустите
docker-compose restart telegram-bot
```

### Webhook не работает

```bash
# Проверьте, что порт 8081 открыт
netstat -an | grep 8081

# Проверьте логи webhook сервера
docker-compose logs telegram-bot | grep webhook
```

### Тесты падают

```bash
# Убедитесь, что все зависимости установлены
pip install -r requirements.txt

# Проверьте подключение к тестовой БД
export TEST_DATABASE_URL=postgresql://...
pytest tests/unit/ -v -s
```

---

## 🚀 Разработка

### Структура проекта для разработки

```
bot/                    # Aiogram 3 бот
├── main.py            # Точка входа
├── handlers/          # Роутеры с handlers
├── middlewares/       # Middleware (DB, User)
├── keyboards/         # Inline клавиатуры
├── states/            # FSM состояния
└── webhook_server.py  # Webhook сервер (порт 8081)

config/                # Конфигурация
└── settings.py        # Pydantic Settings

database/              # SQLAlchemy 2.0
├── models.py          # ORM модели
├── base.py            # Engine, session, init_db
└── crud.py            # CRUD операции

services/              # Business logic
└── hiddify_client.py  # Async Hiddify API клиент

tests/                 # Тесты
└── unit/
    └── test_handlers.py
```

### Добавление нового handler

1. Создайте функцию в `bot/handlers/<module>_handlers.py`
2. Зарегистрируйте роутер в `bot/main.py`:
   ```python
   from bot.handlers.<module>_handlers import <name>_router
   dp.include_router(<name>_router)
   ```
3. Перезапустите бота

---

## 📝 Environment Variables Reference

| Переменная | Обязательная | Описание | Пример |
|-------------|---------------|----------|--------|
| `BOT_TOKEN` | ✅ | Telegram Bot Token | `123456:ABC-DEF...` |
| `BOT_USERNAME` | ✅ | Имя бота (без @) | `SKRTvpnbot` |
| `ADMIN_IDS` | ✅ | ID администраторов (JSON список) | `[123456, 789012]` |
| `POSTGRES_HOST` | ✅ | DB хост | `localhost` |
| `POSTGRES_PORT` | ✅ | DB порт | `5432` |
| `POSTGRES_DB` | ✅ | DB имя | `hiddify_bot` |
| `POSTGRES_USER` | ✅ | DB пользователь | `hiddify_user` |
| `POSTGRES_PASSWORD` | ✅ | DB пароль | `secure_password` |
| `PANEL_DOMAIN` | ✅ | Hiddify панель домен | `panel.yourvpn.ru` |
| `HIDDIFY_API_TOKEN` | ✅ | Hiddify API токен | `your_api_token` |
| `REDIS_HOST` | ✅ | Redis хост | `localhost` |
| `REDIS_PORT` | ✅ | Redis порт | `6379` |
| `REDIS_PASSWORD` | ✅ | Redis пароль | `redis_password` |
| `CRYPTOBOT_API_TOKEN` | ❌ | CryptoBot токен | `your_token` |
| `SECRET_KEY` | ✅ | Секретный ключ | `change-me` |
