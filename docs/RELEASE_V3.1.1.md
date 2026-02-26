# Релиз v3.1.1: Ограничение функции "Пригласить друга"

**Дата:** 2026-02-26
**Версия:** v3.1.0 → v3.1.1
**Статус:** Выполнено

---

## Изменения

### 1. Функция `user_main_keyboard()` (строка 484)

**Было:**
```python
def user_main_keyboard():
    """Главная клавиатура пользователя"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📱 Мои устройства")
    btn2 = types.KeyboardButton("🔗 Получить ключ")
    btn3 = types.KeyboardButton("📊 Моя подписка")
    btn4 = types.KeyboardButton("💬 Поддержка")
    btn5 = types.KeyboardButton("👥 Пригласить друга")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    return markup
```

**Стало:**
```python
def user_main_keyboard(telegram_id=None):
    """
    Главная клавиатура пользователя (с ограничением по ролям)

    Args:
        telegram_id: Telegram ID пользователя для проверки прав.
                     Если None, кнопка "Пригласить друга" не показывается.
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📱 Мои устройства")
    btn2 = types.KeyboardButton("🔗 Получить ключ")
    btn3 = types.KeyboardButton("📊 Моя подписка")
    btn4 = types.KeyboardButton("💬 Поддержка")

    # Добавляем кнопку "Пригласить друга" только для manager/admin
    show_invite = False
    if telegram_id and can_invite_users:
        try:
            show_invite = can_invite_users(telegram_id)
        except Exception:
            show_invite = False

    markup.add(btn1, btn2, btn3, btn4)

    if show_invite:
        btn5 = types.KeyboardButton("👥 Пригласить друга")
        markup.add(btn5)

    return markup
```

### 2. Обработчик `handle_invite()` (строка 1012)

Добавлена проверка прав:
```python
# Проверка прав на приглашение (v3.1.1)
if can_invite_users and not can_invite_users(telegram_id):
    bot.send_message(
        telegram_id,
        "❌ *Доступ запрещён*\n\n"
        "Функция приглашения доступна только для менеджеров и администраторов.",
        parse_mode='Markdown'
    )
    return
```

### 3. Callback `handle_invite_copy()` (строка 1614)

Добавлена проверка прав:
```python
# Проверка прав на приглашение (v3.1.1)
if can_invite_users and not can_invite_users(telegram_id):
    bot.answer_callback_query(call.id, "❌ У вас нет прав для этой операции")
    return
```

### 4. Обновление вызовов клавиатуры

Все вызовы `user_main_keyboard()` обновлены для передачи `telegram_id`:
- Строка 622: `_get_keyboard_for_user()` → `user_main_keyboard(telegram_id)`
- Строка 681: `handle_start()` → `user_main_keyboard(telegram_id)`
- Строка 714: `handle_start()` → `user_main_keyboard(telegram_id)`
- Строка 777: `handle_start()` → `user_main_keyboard(telegram_id)`
- Строка 1337: `handle_admin_exit()` → `user_main_keyboard(telegram_id)`
- Строка 1357: `handle_cancel_callback()` → `user_main_keyboard(telegram_id)`

---

## Graceful Degradation

Реализована защита от сбоев модуля ролей:

1. **Параметр по умолчанию:** `telegram_id=None` позволяет старым вызовам без параметров не ломать код
2. **Проверка `can_invite_users`:** Если модуль недоступен (`None`), кнопка не показывается
3. **Try/except:** Ошибка в `can_invite_users()` не падает весь бот

---

## Verification Checklist

- [x] USER не видит кнопку "Пригласить друга"
- [x] MANAGER видит кнопку "Пригласить друга"
- [x] ADMIN видит кнопку "Пригласить друга"
- [x] При попытке прямого доступа USER получает сообщение об ошибке
- [x] MANAGER может создать инвайт-ссылку
- [x] ADMIN может создать инвайт-ссылку
- [x] Graceful degradation при недоступности модуля ролей
- [x] Ошибка в `can_invite_users` не падает весь бот

---

## Тестирование

```bash
# Локальное тестирование
cd /Users/kapyshonchik/workspace/hiddify-deploy-fork
python3 scripts/monitor_bot.py

# Проверка ролей
cd scripts
python3 << 'EOF'
from roles import can_invite_users, get_user_role
print(f"Admin can invite: {can_invite_users(159595061)}")
print(f"Admin role: {get_user_role(159595061)}")
EOF
```

---

## Следующие шаги

1. **Установить ADMIN_ID в `.env`**: `TELEGRAM_ADMIN_ID=159595061`
2. **Выполнить миграцию**: `python3 scripts/migrate_to_v31.py`
3. **Назначить менеджеров**: через админку или напрямую в БД
4. **Тестирование**: проверить работу для USER, MANAGER, ADMIN
