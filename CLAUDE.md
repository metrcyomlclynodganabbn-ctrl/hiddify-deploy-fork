# Hiddify Bot — контекст проекта

## Что это
Telegram-бот для управления VPN-сервисом на базе Hiddify/3X-UI.
Бот: @SKRTvpnbot | Сервер: 5.45.114.73 (kodu-3xui) | SSH пароль: ~/.mcp-env

## Текущая версия: v4.0.0 → v5.0.0 (в разработке)
Задеплоена в Docker. Код в origin/main. 53 теста проходят.

### 🔄 РЕФАКТОРИНГ НА AIOGRAM 3 (в разработке)

**Статус миграции**:
- ✅ ЭТАП 1: Фундамент и структура проекта (completed)
  - Создана структура `bot/`, `config/`, `database/`, `services/`, `utils/`
  - `config/settings.py` — Pydantic Settings
- ✅ ЭТАП 2: База данных PostgreSQL + SQLAlchemy (completed)
  - `database/models.py` — 7 моделей (User, Subscription, Payment, SupportTicket, TicketMessage, Referral, Invite)
  - `database/base.py` — async engine + session maker + init_db
  - `database/crud.py` — 33 async CRUD функции
- ✅ ЭТАП 3: Async Hiddify API клиент (completed)
  - `services/hiddify_client.py` — httpx async wrapper, 336 строк
  - Методы: create_user, get_users, update_user, delete_user, get_stats
- ✅ ЭТАП 4.1: Aiogram 3 архитектура - entry point (completed)
  - `bot/main.py` — точка входа с middleware pipeline
  - `bot/middlewares/db_middleware.py` — AsyncSession инъекция
  - `bot/middlewares/user_middleware.py` — get_or_create_user, block check
- ✅ ЭТАП 4.2: Middleware + FSM states + Keyboards (completed)
  - Полная реализация middlewares
  - `bot/states/user_states.py` — 10 FSM State groups (108 lines)
  - `bot/keyboards/user_keyboards.py` — 22 keyboard functions (VLESS only)
  - `bot/filters/admin_filter.py` — IsAdmin, IsAdminUser filters
- ✅ ЭТАП 5.1: /start handler (completed)
  - Full /start implementation with invite codes and referrals
  - /help, /cancel, /profile handlers
- ✅ ЭТАП 5.2: Other user handlers (completed)
  - "Мои устройства" handler (handle_my_devices) - show active connections from Hiddify API
  - "Получить ключ" handler (handle_get_key + callbacks) - protocol selection (VLESS Reality only), platform selection
  - "Моя подписка" handler (handle_my_subscription + callbacks) - subscription status, trial activation (7 days, 5 GB)
  - "Поддержка" handler (handle_support + FSM callbacks) - ticket creation flow with TicketStates
  - "Пригласить друга" handler (handle_invite_friend + callbacks) - referral link and stats
- ✅ ЭТАП 5.3: Admin handlers (completed)
  - User management (handle_admin_users) - show users list (first 20 of 50)
  - Create User (handle_admin_create_user + FSM) - username input, confirmation
  - User Info (callback_user_info) - detailed user stats with keyboard
  - Extend Subscription (callback_user_extend) - +30 days to expiry
  - Block/Unblock (callback_user_block, callback_user_unblock) - toggle user block
  - Set Limit (callback_user_limit + FSM) - change traffic limit
  - Statistics (handle_admin_stats) - system stats with Hiddify API integration
  - Invite Management (handle_admin_invites + callbacks) - create codes, list, stats
  - Support Tickets (handle_admin_tickets) - stub for ticket management
  - Broadcast (handle_admin_broadcast) - stub for broadcast system
- ✅ ЭТАП 5.4.1: CryptoBot payments (completed)
  - Payment handlers (payment_handlers.py) - plan selection, invoice creation
  - CryptoBot API integration (createInvoice, getInvoices)
  - Webhook server (webhook_server.py) - aiohttp on port 8081
  - Payment status tracking (pending → completed)
  - Subscription activation after payment
  - Manual payment check button
- ✅ ЭТАП 5.4.2: Telegram Stars payments (completed)
  - sendInvoice() API integration
  - Pre-checkout query handler (pre_checkout_stars)
  - Successful payment handler (on_successful_payment)
  - Pricing: 200/700/1700 XTR (weekly/monthly/quarterly)
  - PaymentProvider.TELEGRAM_STARS enum
  - Idempotent processing (duplicate protection)
- ⏳ ЭТАП 5.4.3: Promo code system (next)
  - Promo code validation
  - Discount application

**Новая точка входа** (будет после завершения):
- Старый: `scripts/monitor_bot.py` (Telebot)
- Новый: `bot/main.py` (Aiogram 3)

## Структура (новая + старая)

    # НОВАЯ — Aiogram 3 (в разработке)
    bot/               — Aiogram 3 бот
      main.py          — новая точка входа
      handlers/        — роутеры с handlers
      middlewares/     — middleware pipeline
      keyboards/       — клавиатуры
      states/          — FSM состояния
    config/
      settings.py      — Pydantic Settings
    database/          — SQLAlchemy 2.0 async
      models.py        — ORM модели
      base.py          — engine + session maker
      crud.py          — CRUD операции
    services/          — Business logic
      hiddify_client.py — Async Hiddify API ✅ (VLESS Reality only)

    # СТАРАЯ — Telebot (сохранена для совместимости)
    scripts/
      monitor_bot.py   — точка входа (deprecated)
      v4_handlers.py   — v4.0 handlers
      hiddify_api.py   — sync API client (deprecated)
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
