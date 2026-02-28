# Задачи Hiddify Bot v4.0

## Сессия 2026-03-01

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
70c5981 [fix] Fix callback indentation in handle_ticket_category
c8af5ff [fix] Fix imports for Docker container - add scripts. prefix
2d31cba [fix] Escape Markdown special chars in username
```

## Следующие шаги

1. Investigate & fix health check endpoint (порт 8080)
2. Настроить переменные окружения для Stripe и Grafana
3. Протестировать v4.0 функциональность
4. Написать интеграционные тесты
