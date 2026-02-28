# Hiddify Bot — контекст проекта

## Что это
Telegram-бот для управления VPN-сервисом на базе Hiddify/3X-UI.
Бот: @SKRTvpnbot | Сервер: 5.45.114.73 (kodu-3xui) | SSH пароль: ~/.mcp-env

## Текущая версия: v4.0.0
Задеплоена в Docker. Код в origin/main. 53 теста проходят.

## ТОЧКА ВХОДА бота
scripts/monitor_bot.py — главный файл, с него стартует контейнер.

## Структура

    scripts/           — весь Python-код бота
      monitor_bot.py   — точка входа
      v4_handlers.py   — платежи, поддержка, рефералы (v4.0)
      hiddify_api.py   — API клиент Hiddify
      database/        — SQLAlchemy models
      payments/        — Stripe + промокоды
      support/         — тикеты поддержки
      referral/        — реферальная система
      cache/           — Redis клиент
      monitoring/      — health endpoint + Prometheus metrics
    infrastructure/
      docker/          — docker-compose.yml + Dockerfile
    migrations/        — SQL: v2.1, v3.1
    tests/
      unit/            — unit-тесты
      integration/     — интеграционные тесты
    docs/              — BOT_UI_SPEC.md, DEPLOYMENT_v4.md
    configs/           — JSON/YAML конфиги протоколов

## Статус на 2026-03-01 (обновлено)

### Контейнеры
- ✅ postgres: healthy (Up 47+ hours)
- ✅ redis: healthy (Up 47+ hours)
- ✅ telegram-bot: работает, v4.0 модули загружены
- ✅ prometheus: работает (порт 9091)
- ✅ grafana: работает (порт 3000)

### v4.0 модули
- ✅ Redis клиент: подключен
- ✅ Stripe клиент: инициализирован (WARNING: STRIPE_SECRET_KEY не установлен)
- ✅ Prometheus metrics: запущен на порту 9090
- ⚠️ Health check endpoint: запущен на порту 8080, но не отвечает на запросы
- ✅ Payment handlers: зарегистрированы
- ✅ Support handlers: зарегистрированы
- ✅ Referral handlers: зарегистрированы
- ✅ Config builders: зарегистрированы

### Последние исправления (2026-03-01)
1. ✅ Исправлен незакрытый Markdown-тег в handle_confirm_create_user
   - Добавлена функция escape_markdown() для экранирования спецсимволов
   - username теперь экранируется перед вставкой в Markdown
2. ✅ Исправлены импорты для Docker-контейнера
   - Все локальные модули теперь импортируются с префиксом 'scripts.'
   - v4.0 модули успешно загружаются в контейнере
3. ✅ Исправлен отступ в v4_handlers.py
   - bot.answer_callback_query(callback.id) перемещён внутрь функции

### Известные проблемы
1. ⚠️ Health check endpoint (порт 8080): запущен, но не отвечает на HTTP-запросы
   - Логи показывают: "Health check endpoint запущен на порту 8080"
   - curl http://localhost:8080/health — timeout
   - Возможно, aiohttp сервер не корректно инициализирован в асинхронном режиме
2. ⚠️ GRAFANA_ADMIN_PASSWORD не задан в .env на сервере (warning при docker-compose)

## Команды для работы с сервером

Проверить логи бота:
    sshpass -p P8mFfFvE3d92d3Ln ssh root@5.45.114.73 "cd /opt/hiddify-manager/infrastructure/docker && docker-compose logs telegram-bot --tail=30"

Ребилд бота:
    sshpass -p P8mFfFvE3d92d3Ln ssh root@5.45.114.73 "cd /opt/hiddify-manager/infrastructure/docker && docker-compose up -d --build telegram-bot"

Статус контейнеров:
    sshpass -p P8mFfFvE3d92d3Ln ssh root@5.45.114.73 "cd /opt/hiddify-manager/infrastructure/docker && docker-compose ps"

## Запуск тестов
    pytest tests/unit/ -v
    pytest tests/integration/ -v

## Что НЕ трогать
- /opt/hiddify-manager/data/bot.db — боевая база данных с пользователями
- .env на сервере — содержит реальные пароли
- backups/ на сервере — резервные копии БД
