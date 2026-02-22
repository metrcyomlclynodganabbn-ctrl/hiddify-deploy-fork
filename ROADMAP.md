# 🗺️ ROADMAP - План развития Hiddify Manager Auto-Deploy

**Версия**: 2.1 → 3.0
**Дата**: 23 февраля 2026
**Статус**: В разработке

---

## 📊 Текущее состояние (v2.0)

### ✅ Завершено
- Hiddify Manager v8 с базовыми протоколами
- Telegram-бот v2.0 (819 строк, aiogram 3.x)
- SQLite БД с 3 таблицами
- Инвайт-система регистрации
- Базовый пользовательский UI (5 разделов)
- Админ-панель (6 разделов)
- Production tuning конфиги

### ❌ Что отсутствует (по сравнению с VPN-SRV)
1. QR код генерация для быстрого импорта
2. Текстовый ключ/URL для копирования
3. Детальные инструкции для платформ
4. Пробный период (7 дней)
5. Расширенная статистика с прогресс-баром
6. Партнёрская программа
7. Тикетная система поддержки
8. Оплата (Telegram Stars)
9. Автоматическая генерация VLESS-ссылок
10. Rotation SNI/dest без перезагрузки

---

## 🎯 Приоритеты улучшений

### КРИТИЧЕСКИЕ (v2.1) - внедрить немедленно

#### 1. QR код и текстовый ключ
**Проблема**: Пользователям不方便 импортировать конфиги вручную

**Решение**:
```python
# Добавить в requirements.txt
qrcode>=8.0
pillow>=10.0

# Добавить в bot.py
import qrcode
from io import BytesIO
from aiogram.types import BufferedInputFile

async def generate_qr_code(url: str) -> BufferedInputFile:
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return BufferedInputFile(buffer.getvalue(), filename="qr_code.png")
```

**Изменения в БД**: не требуются

#### 2. VLESS URL генерация
**Проблема**: Нет единообразного формата ссылок

**Решение** (изучено из setup-xray-reality.sh):
```python
def generate_vless_url(
    uuid: str,
    ip: str,
    port: int,
    public_key: str,
    short_id: str,
    sni: str = "www.apple.com",
    fingerprint: str = "chrome"
) -> str:
    """
    Генерирует VLESS-Reality ссылку в формате:
    vless://uuid@ip:port?encryption=none&flow=xtls-rprx-vision&security=reality&sni=SNI&fp=chrome&pbk=PBK&sid=SID&type=tcp#Label
    """
    base = f"vless://{uuid}@{ip}:{port}"
    params = (
        f"?encryption=none&flow=xtls-rprx-vision&security=reality"
        f"&sni={sni}&fp={fingerprint}"
        f"&pbk={public_key}&sid={short_id}&type=tcp"
    )
    return f"{base}{params}#{sni}"
```

**Изменения в БД**: добавить поля в таблицу `users`:
```sql
ALTER TABLE users ADD COLUMN reality_public_key TEXT;
ALTER TABLE users ADD COLUMN reality_short_id TEXT;
ALTER TABLE users ADD COLUMN reality_sni TEXT DEFAULT 'www.apple.com';
```

#### 3. Инструкции для платформ
**Проблема**: Пользователи не знают, как подключаться

**Решение** (VPN-SRV experience):
```python
PLATFORM_INSTRUCTIONS = {
    "ios": """
📱 **Инструкция для iOS**

1. Скачайте Nekobox из App Store
2. Нажмите "+" → "Import from Clipboard"
3. Вставьте ссылку ниже
4. Подключитесь к серверу
    """,

    "android": """
🤖 **Инструкция для Android**

1. Скачайте Nekobox из Google Play
2. Нажмите "+" → "Import from Clipboard"
3. Вставьте ссылку ниже
4. Подключитесь к серверу
    """,

    "windows": """
💻 **Инструкция для Windows**

1. Скачайте Nekobox с GitHub
2. Распакуйте и запустите Nekobox.exe
3. Нажмите "+" → "Import from Clipboard"
4. Вставьте ссылку ниже
5. Подключитесь к серверу
    """,

    "macos": """
🍎 **Инструкция для macOS**

1. Скачайте Nekobox с GitHub
2. Откройте загруженный DMG файл
3. Перетащите Nekobox в Applications
4. Запустите, нажмите "+" → "Import from Clipboard"
5. Вставьте ссылку ниже
6. Подключитесь к серверу
    """
}
```

**Изменения в БД**: не требуются

#### 4. Пробный период
**Проблема**: Нет способа протестировать перед покупкой

**Решение** (VPN-SRV experience):
```python
# Добавить в БД
ALTER TABLE users ADD COLUMN is_trial BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN trial_expiry TIMESTAMP;

# Логика в боте
async def start_trial_period(user_id: int, days: int = 7):
    subscription = get_user_subscription(user_id)
    subscription.is_trial = True
    subscription.trial_expiry = datetime.now() + timedelta(days=days)
    subscription.data_limit_bytes = 10 * (1024**3)  # 10 GB
    commit()
```

**Изменения в БД**: см. выше

---

## 🚀 ВАЖНЫЕ (v2.2) - ближайшее время

#### 5. Расширенная статистика
**Решение**:
```python
async def show_user_stats(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    subscription = get_active_subscription(user.id)

    used_gb = subscription.used_bytes / (1024**3)
    total_gb = subscription.data_limit_bytes / (1024**3)
    percentage = (used_gb / total_gb) * 100

    progress_bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))

    await callback.message.edit_text(
        f"📊 **Ваша подписка**\n\n"
        f"📅 Истекает: {subscription.expires_at:%d.%m.%Y}\n"
        f"📊 Трафик:\n"
        f"{progress_bar} {percentage:.1f}%\n"
        f"{used_gb:.2f} GB / {total_gb:.2f} GB\n\n"
        f"⏰ Осталось дней: {(subscription.expires_at - datetime.now()).days}"
    )
```

#### 6. Партнёрская программа (базовая)
**Решение** (VPN-SRV 4-level → упрощённая 1-level):
```sql
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER REFERENCES users(id),
    referred_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE partner_earnings (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES users(id),
    amount DECIMAL(10,2),
    payment_id INTEGER,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, paid
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Комиссия**: 20% от первой оплаты реферала

#### 7. Тикетная система
**Решение**:
```sql
CREATE TABLE support_tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    category VARCHAR(50),  -- payment, connection, speed, app, other
    status VARCHAR(20) DEFAULT 'open',  -- open, in_progress, closed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ticket_messages (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES support_tickets(id),
    sender_id INTEGER REFERENCES users(id),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 8. Оплата Telegram Stars
**Решение**:
```python
from aiogram.types import LabeledPrice

async def create_payment_invoice(message: Message):
    prices = [LabeledPrice(
        label="Подписка 30 дней (100 GB)",
        amount=100  # Stars
    )]

    await message.answer_invoice(
        title="VPN подписка",
        description="30 дней, 100 GB трафика",
        payload="subscription_30",
        provider_token="",  # Empty for Stars
        currency="XTR",  # Stars
        prices=prices
    )
```

---

## 🔧 ЖЕЛАТЕЛЬНЫЕ (v3.0) - перспектива

#### 9. Автоматическая генерация ключей Reality
**Решение** (из setup-xray-reality.sh):
```python
import subprocess
import json

def generate_reality_keys():
    """Генерирует X25519 ключи для Reality"""
    result = subprocess.run(
        ["/usr/local/bin/xray", "x25519"],
        capture_output=True,
        text=True
    )

    output = result.stdout
    private_key = next(line.split(": ")[1] for line in output.split("\n") if "Private key" in line)
    public_key = next(line.split(": ")[1] for line in output.split("\n") if "Public key" in line)

    short_id = secrets.token_hex(8)

    return {
        "private_key": private_key,
        "public_key": public_key,
        "short_id": short_id
    }
```

#### 10. Rotation SNI без перезагрузки
**Решение** (hot reload config):
```python
async def rotate_sni(dest: str, server_names: List[str]):
    """Меняет SNI без перезагрузки Xray"""
    cfg = load_xray_config()
    cfg["inbounds"][0]["streamSettings"]["realitySettings"]["dest"] = dest
    cfg["inbounds"][0]["streamSettings"]["realitySettings"]["serverNames"] = server_names
    save_xray_config(cfg)

    # Xray автоматически перечитывает конфиг
    # Или можно отправить SIGHUP для reload
```

#### 11. Антифрод система
**Решение**:
```python
async def check_fraud(user_id: int, action: str) -> bool:
    """Проверяет подозрительную активность"""
    # Проверить множественные регистрации с одного IP
    # Проверить множественные trial периоды
    # Проверить аномальные паттерны

    if is_suspicious(user_id):
        log_fraud_attempt(user_id, action)
        return True
    return False
```

---

## 📋 ПЛАН РЕАЛИЗАЦИИ

### v2.1 (Февраль 2026) - Критические улучшения
- [ ] QR код генерация
- [ ] Текстовый ключ/URL
- [ ] Инструкции для платформ
- [ ] Пробный период 7 дней
- [ ] VLESS URL генерация
- [ ] Обновить requirements.txt
- [ ] Миграция БД (добавить поля)
- [ ] Обновить BOT_UI_SPEC.md

### v2.2 (Март 2026) - Важные улучшения
- [ ] Расширенная статистика
- [ ] Партнёрская программа (базовая)
- [ ] Тикетная система
- [ ] Оплата Telegram Stars
- [ ] Миграция БД (новые таблицы)
- [ ] Обновить админ-панель

### v3.0 (Апрель-Май 2026) - Желательные улучшения
- [ ] Автоматическая генерация ключей
- [ ] Rotation SNI без перезагрузки
- [ ] Антифрод система
- [ ] Мультиязычность
- [ ] Web-панель для пользователей
- [ ] PostgreSQL миграция

---

## 🔄 Миграция данных

### v2.0 → v2.1
```sql
-- Добавить поля в users
ALTER TABLE users ADD COLUMN reality_public_key TEXT;
ALTER TABLE users ADD COLUMN reality_short_id TEXT;
ALTER TABLE users ADD COLUMN reality_sni TEXT DEFAULT 'www.apple.com';
ALTER TABLE users ADD COLUMN is_trial BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN trial_expiry TIMESTAMP;

-- Миграция существующих пользователей
UPDATE users SET reality_sni = 'www.apple.com' WHERE reality_sni IS NULL;
```

### v2.1 → v2.2
```sql
-- Новые таблицы
CREATE TABLE referrals (...);
CREATE TABLE partner_earnings (...);
CREATE TABLE support_tickets (...);
CREATE TABLE ticket_messages (...);
```

### v2.2 → v3.0
```sql
-- Антифрод
CREATE TABLE fraud_logs (...);

-- Мультиязычность
ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru';
```

---

## 📊 МЕТРИКИ УСПЕХА

### v2.1
- [ ] Уменьшение времени первого подключения < 2 минут
- [ ] Увеличение конверсии trial → платная подписка > 30%
- [ ] Уменьшение тикетов "как подключиться" на 80%

### v2.2
- [ ] Увеличение LTV пользователя
- [ ] Увеличение количества рефералов
- [ ] Уменьшение времени ответа на тикеты < 4 часов

### v3.0
- [ ] Уменьшение detector'ов на 90%
- [ ] Увеличение uptime до 99.9%
- [ ] Поддержка 5+ языков

---

**Примечание**: Все улучшения основаны на анализе:
1. VPN-SRV проекта (~/workspace/VPN-SRV/)
2. Kodu 3X UI документации
3. PDF инструкций по VLESS-Reality 2024-2025
4. Скрипта setup-xray-reality-with-telegram-bot.sh
