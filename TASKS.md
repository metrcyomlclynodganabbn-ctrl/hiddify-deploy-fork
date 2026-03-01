# Задачи Hiddify Bot

## 🔄 РЕФАКТОРИНГ: Telebot → Aiogram 3

**Начато**: 2026-03-01
**Ветка**: `main` (планируется: `refactor/aiogram3-architecture`)
**Референс**: VPN-SRV (`~/workspace/p-stop-projects/VPN-SRV`)

### ✅ Выполнено

- [x] **ЭТАП 1: Фундамент и структура проекта**
  - Создана структура: `bot/`, `config/`, `database/`, `services/`, `utils/`
  - `config/settings.py` — Pydantic Settings (Telegram, DB, Hiddify API, Payments, Redis)
  - Commit: `f989399` — "feat: ЭТАП 2 complete - database layer"

- [x] **ЭТАП 2: База данных PostgreSQL + SQLAlchemy**
  - `database/models.py` — 7 моделей (User, Subscription, Payment, SupportTicket, TicketMessage, Referral, Invite)
  - `database/base.py` — async engine + session maker + init_db + 27 индексов
  - `database/crud.py` — 33 async CRUD функции (user, subscription, payment, support, referral, invite)

- [x] **ЭТАП 3: Async Hiddify API клиент**
  - `services/hiddify_client.py` — httpx async wrapper, 336 строк
  - AsyncHiddifyAPI класс с методами: create_user, get_users, update_user, delete_user, get_stats
  - Глобальный экземпляр: get_hiddify_client()
  - Commit: `15b3143` — "feat: ЭТАП 3+4.1 complete - async Hiddify client + aiogram3 entry point"

- [x] **ЭТАП 4.1: Aiogram 3 архитектура - entry point**
  - `bot/main.py` — точка входа с middleware pipeline
  - `bot/middlewares/db_middleware.py` — AsyncSession инъекция (stub)
  - `bot/middlewares/user_middleware.py` — get_or_create_user, проверка is_blocked (stub)
  - `bot/handlers/user_handlers.py` — заглушки (/start, /help, /cancel, /profile)
  - `bot/handlers/admin_handlers.py` — заглушка (/admin с проверкой admin_ids)
  - `config/logging_config.py` — console + file логирование
  - Commit: `15b3143` — "feat: ЭТАП 3+4.1 complete - async Hiddify client + aiogram3 entry point"

- [x] **ЭТАП 4.2: Middleware + FSM states + Keyboards**
  - `bot/middlewares/db_middleware.py` — full implementation (commit/rollback)
  - `bot/middlewares/user_middleware.py` — full implementation (rate limiting 20/min, 100/hour)
  - `bot/filters/admin_filter.py` — IsAdmin, IsAdminUser filters
  - `bot/states/user_states.py` — 10 FSM State groups (108 lines)
  - `bot/keyboards/user_keyboards.py` — 22 keyboard functions (VLESS only, removed Hysteria2/SS2022)
  - Commit: `df30dc6` — "feat: ЭТАП 4.2-5.1 complete"

- [x] **ЭТАП 5.1: /start handler**
  - Full /start implementation with invite codes (v3.x legacy)
  - Full /start implementation with referrals (v4.0)
  - Admin panel check
  - Block/expiry checks
  - /help, /cancel, /profile handlers
  - VLESS Reality only (removed Hysteria2/SS2022)
  - Commit: `df30dc6` — "feat: ЭТАП 4.2-5.1 complete"

- [x] **ЭТАП 5.2: Other user handlers**
  - "Мои устройства" handler (handle_my_devices) - show active connections from Hiddify API
  - "Получить ключ" handler (handle_get_key + callbacks) - protocol selection (VLESS Reality only), platform selection
  - "Моя подписка" handler (handle_my_subscription + callbacks) - subscription status, trial activation (7 days, 5 GB)
  - "Поддержка" handler (handle_support + FSM callbacks) - ticket creation flow with TicketStates
  - "Пригласить друга" handler (handle_invite_friend + callbacks) - referral link and stats
  - FSM states integration (GetKeyStates, TrialStates, TicketStates, ReferralStates)
  - Commit: `51378a1` — "feat: ЭТАП 5.2 complete - other user handlers"

- [x] **ЭТАП 5.3: Admin handlers**
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
  - FSM states (CreateUserStates, AdminUserStates, InviteStates)
  - Commit: `1e91ecb` — "feat: ЭТАП 5.3 complete - admin handlers"

### ⏳ Следующий шаг

- [ ] **ЭТАП 5.4: Payment handlers**
  - CryptoBot integration (USDT payments)
  - Telegram Stars integration
  - Promo code system
  - Payment status tracking via webhooks

### 🔜 Планируется

- [ ] **ЭТАП 6: Service Layer**

- [ ] **ЭТАП 5+: Перенос handlers**
  - User handlers (start, cancel, devices, get key, subscription, support)
  - Admin handlers
  - Payment handlers (CryptoBot/Telegram Stars вместо Stripe)
  - Support handlers
  - Referral handlers

---

## v4.0 — Старая версия (Telebot)

### Сессия 2026-03-01

### Исправлено [x]

- [x] **Незакрытый Markdown-тег в handle_confirm_create_user**
  - Добавлена функция `escape_markdown()` для экранирования спецсимволов
  - Применено к `username` в сообщениях об успешном создании пользователя
  - Применено к `username` в сообщении о существующем пользователе
  - Commit: `2d31cba`

- [x] **v4.0 модули не загружались в Docker-контейнере**
  - Исправлены импорты в `monitor_bot.py`: добавлен префикс `scripts.` ко всем локальным модулям
  - `from vless_utils` → `from scripts.vless_utils`
  - `from platform_instructions` → `from scripts.platform_instructions`
  - `from qr_generator` → `from scripts.qr_generator`
  - `from hiddify_api` → `from scripts.hiddify_api`
  - `from roles` → `from scripts.roles`
  - Commit: `c8af5ff`

- [x] **Ошибка 'name callback is not defined' в v4_handlers.py**
  - Исправлен отступ в `handle_ticket_category` функции
  - `bot.answer_callback_query(callback.id)` перемещён внутрь функции
  - Commit: `70c5981`

### Осталось [ ]

#### Критичные

- [ ] **Health check endpoint (порт 8080) не отвечает**
  - Логи: "Health check endpoint запущен на порту 8080"
  - Проблема: `curl http://localhost:8080/health` — timeout
  - Возможно: aiohttp сервер не корректно работает в асинхронном режиме
  - Файл: `scripts/monitoring/health.py`
  - Действия:
    - Проверить функцию `start_health_server()`
    - Убедиться, что `await site.start()` выполняется корректно
    - Добавить обработку ошибок

#### Некритичные

- [ ] **STRIPE_SECRET_KEY не установлен**
  - Текущий статус: WARNING в логах, Stripe клиент инициализирован
  - Действия: добавить в `.env` на сервере или отключить warning

- [ ] **GRAFANA_ADMIN_PASSWORD не задан**
  - Текущий статус: warning при docker-compose
  - Действия: добавить в `.env` на сервере

#### Улучшения

- [ ] **Добавить в .env.example переменные для v4.0 модулей**
  - STRIPE_SECRET_KEY
  - GRAFANA_ADMIN_PASSWORD
  - Другие переменные для мониторинга

- [ ] **Проверить работу v4.0 handlers**
  - Протестировать платежи (buy_subscription)
  - Протестировать поддержку (support)
  - Протестировать рефералы (my_referrals)
  - Протестировать config builder (create_config)

- [ ] **Добавить интеграционные тесты для v4.0**
  - Тесты для payment handlers
  - Тесты для support tickets
  - Тесты для referral system
  - Тесты для config builders

---

## Статус тестов

- Unit тесты: 53 проходят
- Интеграционные тесты: ?

## Статус коммитов

```
1e91ecb [feat] ЭТАП 5.3 complete - admin handlers
5dd33df [docs] Update CLAUDE.md and TASKS.md - ЭТАП 5.2 complete
51378a1 [feat] ЭТАП 5.2 complete - other user handlers
70c5981 [fix] Fix callback indentation in handle_ticket_category
c8af5ff [fix] Fix imports for Docker container - add scripts. prefix
2d31cba [fix] Escape Markdown special chars in username
```

## Следующие шаги

1. Investigate & fix health check endpoint (порт 8080)
2. Настроить переменные окружения для Stripe и Grafana
3. Протестировать v4.0 функциональность
4. Написать интеграционные тесты
