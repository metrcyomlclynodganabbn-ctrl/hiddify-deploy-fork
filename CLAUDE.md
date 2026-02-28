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

## Статус на 2026-03-01
- postgres: healthy
- redis: healthy
- telegram-bot: работает, но падает в handle_confirm_create_user —
  незакрытый Markdown-тег в bot.send_message() (~строка 1537 monitor_bot.py)

## Что НЕ работает — чинить в первую очередь
1. handle_confirm_create_user в monitor_bot.py (~строка 1537) —
   Telegram API 400: незакрытый Markdown-тег в тексте сообщения
2. aiohttp health endpoint (порт 8080) — не запущен
3. GRAFANA_ADMIN_PASSWORD не задан в .env на сервере

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
