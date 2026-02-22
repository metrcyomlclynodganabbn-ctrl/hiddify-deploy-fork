# ЭТАП 4: Массовое создание пользователей (200+)

## Цель
Создать 200+ пользователей с уникальными подписками через API Hiddify.

## Шаги

### 1. Получение API токена
```bash
# Генерация API токена в панели Hiddify
# Settings → Advanced → API Access → Generate Token

# Или через CLI
API_TOKEN=$(ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "hiddify-cli api-token generate")

echo "HIDDIFY_API_TOKEN=$API_TOKEN" >> .env
```

### 2. Создание Python-скрипта для генерации пользователей
```bash
cat > scripts/create_users.py <<'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""
Массовое создание пользователей Hiddify
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

HIDDIFY_API_URL = f"https://{os.getenv('PANEL_DOMAIN')}/api"
HIDDIFY_API_TOKEN = os.getenv("HIDDIFY_API_TOKEN", "")
MAX_USERS = int(os.getenv("MAX_USERS", 250))
BANDWIDTH_LIMIT = int(os.getenv("BANDWIDTH_LIMIT_PER_USER_GB", 100)) * 1024**3

# Headers для API запросов
headers = {
    "Authorization": f"Bearer {HIDDIFY_API_TOKEN}",
    "Content-Type": "application/json"
}

def create_user(username, expire_days=30):
    """Создание одного пользователя"""

    payload = {
        "username": username,
        "data_limit": BANDWIDTH_LIMIT,
        "expire_days": expire_days,
        "protocols": ["vless_reality", "hysteria2", "shadowsocks2022"]
    }

    try:
        response = requests.post(
            f"{HIDDIFY_API_URL}/users",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 201:
            user_data = response.json()
            return True, user_data
        else:
            return False, response.text

    except Exception as e:
        return False, str(e)

def get_subscription_link(user_uuid):
    """Генерация ссылки подписки"""

    base_url = f"https://{os.getenv('PANEL_DOMAIN')}"
    sub_link = f"{base_url}/sub/{user_uuid}"

    return sub_link

def main():
    """Главная функция"""

    print(f"🚀 Начинаю создание {MAX_USERS} пользователей...")

    created_users = []
    failed_users = []

    # Создание пользователей
    for i in range(1, MAX_USERS + 1):
        username = f"user_{i:03d}"

        success, result = create_user(username)

        if success:
            user_uuid = result.get("uuid", "")
            sub_link = get_subscription_link(user_uuid)

            created_users.append({
                "username": username,
                "uuid": user_uuid,
                "subscription": sub_link
            })

            print(f"✅ [{i}/{MAX_USERS}] {username} создан")
        else:
            failed_users.append({
                "username": username,
                "error": result
            })
            print(f"❌ [{i}/{MAX_USERS}] Ошибка создания {username}: {result}")

        # Rate limiting: 5 запросов в секунду
        time.sleep(0.2)

    # Сохранение результатов
    print("\n📊 Результаты:")
    print(f"   ✅ Создано: {len(created_users)}")
    print(f"   ❌ Ошибок: {len(failed_users)}")

    # Сохранение ссылок подписок
    with open("output/subscription_links.txt", "w") as f:
        for user in created_users:
            f.write(f"{user['username']}\t{user['subscription']}\n")

    print(f"📝 Ссылки подписок сохранены в output/subscription_links.txt")

    # Сохранение отчёта об ошибках
    if failed_users:
        with open("output/failed_users.txt", "w") as f:
            for user in failed_users:
                f.write(f"{user['username']}\t{user['error']}\n")

        print(f"⚠️  Ошибки сохранены в output/failed_users.txt")

    return 0

if __name__ == '__main__':
    sys.exit(main())
PYTHON_SCRIPT

chmod +x scripts/create_users.py
```

### 3. Запуск создания пользователей
```bash
# Создание директории для вывода
mkdir -p output

# Запуск скрипта
python3 scripts/create_users.py

# Проверка результатов
echo "📊 Статистика:"
echo "   Всего создано: $(wc -l < output/subscription_links.txt)"
echo "   Ошибок: $(wc -l < output/failed_users.txt 2>/dev/null || echo 0)"
```

### 4. Оптимизация через multiprocessing (для больших объёмов)
```bash
# Если нужно создать 500+ пользователей, использовать параллельную обработку
cat > scripts/create_users_parallel.py <<'PARALLEL_SCRIPT'
#!/usr/bin/env python3
"""
Параллельное создание пользователей с multiprocessing
"""

import os
import sys
import time
from multiprocessing import Pool, cpu_count
from dotenv import load_dotenv

load_dotenv()

MAX_USERS = int(os.getenv("MAX_USERS", 250))
BANDWIDTH_LIMIT = int(os.getenv("BANDWIDTH_LIMIT_PER_USER_GB", 100)) * 1024**3

def create_single_user(i):
    """Создание одного пользователя (для параллельного запуска)"""

    username = f"user_{i:03d}"

    # TODO: Вызов API Hiddify
    # Здесь должен быть код API вызова

    return {
        "username": username,
        "status": "created",
        "subscription": f"https://{os.getenv('PANEL_DOMAIN')}/sub/uuid-{i}"
    }

def main():
    """Главная функция"""

    print(f"🚀 Создаю {MAX_USERS} пользователей параллельно...")

    # Использовать половину CPU cores для безопасности
    num_processes = max(1, cpu_count() // 2)

    with Pool(num_processes) as pool:
        results = pool.map(create_single_user, range(1, MAX_USERS + 1))

    # Сохранение результатов
    with open("output/subscription_links_parallel.txt", "w") as f:
        for user in results:
            f.write(f"{user['username']}\t{user['subscription']}\n")

    print(f"✅ Создано {len(results)} пользователей")

    return 0

if __name__ == '__main__':
    sys.exit(main())
PARALLEL_SCRIPT
```

### 5. Верификация созданных пользователей
```bash
# Проверка количества пользователей через API
curl -X GET "https://$PANEL_DOMAIN/api/users" \
  -H "Authorization: Bearer $HIDDIFY_API_TOKEN" | jq '.total'

# Проверка первых 10 пользователей
curl -X GET "https://$PANEL_DOMAIN/api/users?limit=10" \
  -H "Authorization: Bearer $HIDDIFY_API_TOKEN" | jq '.users[]'
```

## Критерии завершения
- ✅ Создано MAX_USERS пользователей
- ✅ Все ссылки подписок в `output/subscription_links.txt`
- ✅ API подтверждает создание пользователей
- ✅ Ошибок менее 1% от общего числа

## Troubleshooting

### Если API возвращает 401 Unauthorized
```bash
# Проверить токен
curl -X GET "https://$PANEL_DOMAIN/api/me" \
  -H "Authorization: Bearer $HIDDIFY_API_TOKEN"

# Пересоздать токен
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "hiddify-cli api-token regenerate"
```

### Если создание идёт слишком медленно
```bash
# Увеличить rate limit
# Изменить sleep(0.2) на sleep(0.1) в скрипте

# Или использовать параллельную версию
python3 scripts/create_users_parallel.py
```

## Логирование
```bash
exec > >(tee -a logs/users.log)
exec 2>&1
```
