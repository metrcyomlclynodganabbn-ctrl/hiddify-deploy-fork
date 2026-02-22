# VLESS-XTLS-Reality Configuration
# Актуальная конфигурация на 2024-2025 (на основе инструкций)

## Параметры Reality (обновлено)

### Fingerprints (оптимизировано для антидетекта)

```json
{
  "realitySettings": {
    "dest": "www.apple.com:443",
    "serverNames": [
      "apple.com",
      "www.apple.com",
      "icloud.com"
    ],
    "privateKey": "{{private_key}}",
    "shortIds": ["", "2c4d7c0e", "d8b81723", "0a9b54c5"],
    "fingerprint": "chrome"  // или "safari", "firefox", "ios"
  }
}
```

### Доступные fingerprint (по убыванию антидетекта)

| Fingerprint | Описание | Приоритет |
|-------------|-----------|-----------|
| `chrome` | Chrome 103+ | ⭐⭐⭐⭐⭐ |
| `ios` | Safari на iOS 15+ | ⭐⭐⭐⭐⭐ |
| `safari` | Safari на macOS | ⭐⭐⭐⭐ |
| `firefox` | Firefox 105+ | ⭐⭐⭐⭐ |
| `edge` | Edge 105+ | ⭐⭐⭐ |
| `randomized` | Рандомизированный | ⭐⭐ |

### Flow параметры

```json
{
  "flow": "xtls-rprx-vision",
  "flowShow": false
}
```

**Важные замечания:**
- `xtls-rprx-vision` — наиболее стабильный для мобильных сетей РФ
- `flowShow: false` — скрывает flow от провайдера (безопасность)
- Не работает с UDP напрямую (требует support UDP в sniffing)

---

## 🔧 Полная конфигурация inbounds

### VLESS-XTLS-Reality (рекомендуется)

```json
{
  "inbounds": [
    {
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "{{uuid}}",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "dest": "www.apple.com:443",
          "serverNames": [
            "apple.com",
            "www.apple.com",
            "icloud.com"
          ],
          "privateKey": "{{private_key}}",
          "shortIds": ["", "2c4d7c0e", "d8b81723", "0a9b54c5"],
          "fingerprint": "chrome"
        },
        "tcpSettings": {
          "acceptProxyProtocol": false,
          "header": {
            "type": "none"
          }
        }
      }
    }
  ]
}
```

### VLESS-XTLS-Reality (Fallback для проблемных сетей)

```json
{
  "inbounds": [
    {
      "port": 8443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "{{uuid}}",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "dest": "www.microsoft.com:443",
          "serverNames": [
            "microsoft.com",
            "www.microsoft.com",
            "windowsupdate.com"
          ],
          "privateKey": "{{private_key}}",
          "shortIds": ["1c4d7c0e"],
          "fingerprint": "chrome"
        }
      }
    }
  ]
}
```

---

## 📱 Клиентские конфигурации

### V2RayN / v2rayNG (Windows/Android)

```json
{
  "address": "{{server_ip}}",
  "port": 443,
  "uuid": "{{uuid}}",
  "flow": "xtls-rprx-vision",
  "network": "tcp",
  "tls": true,
  "sni": "apple.com",
  "fingerprint": "chrome",
  "realitySettings": {
    "publicKey": "{{public_key}}",
    "shortId": "2c4d7c0e",
    "spiderX": "/"
  }
}
```

### iOS (Shadowrocket / Quantumult X)

```
vless://{{uuid}}@{{server_ip}}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=apple.com&fp=chrome&pbk={{public_key}}&sid=2c4d7c0e&type=tcp#Reality%20Vision
```

### macOS (ClashX / Clash Verge)

```yaml
proxies:
  - name: "Reality-Vision"
    type: vless
    server: {{server_ip}}
    port: 443
    uuid: {{uuid}}
    network: tcp
    tls: true
    udp: true
    flow: xtls-rprx-vision
    servername: apple.com
    reality-opts:
      public-key: {{public_key}}
      short-id: 2c4d7c0e
    fingerprint: chrome
```

---

## 🛡️ Безопасность и антидетект

### Multi-Fingerprint стратегия

Для максимальной антидетекции можно использовать разные fingerprint для разных shortId:

```json
{
  "clients": [
    {
      "id": "{{uuid_1}}",
      "flow": "xtls-rprx-vision",
      "email": "chrome_user@example.com"
    },
    {
      "id": "{{uuid_2}}",
      "flow": "xtls-rprx-vision",
      "email": "ios_user@example.com"
    }
  ]
}
```

### Смена fingerprint при проблемах

Если один fingerprint детектится:
1. Сменить fingerprint: chrome → ios → safari
2. Сменить dest: apple.com → microsoft.com → cloudflare.com
3. Сгенерировать новые shortIds

---

## 🔄 Генерация ключей

### Создание пары ключей

```bash
# На сервере
xray x25519

# Пример вывода:
# Private key: <private_key>
# Public key: <public_key>
# Private key: U桂花s8桂花...
# Public key: q花生s3花生...

# Сохранить private_key в конфиг сервера
# Public key использовать в клиентских конфигах
```

### Генерация shortIds

```bash
# Генерация random shortId (16-бит hex)
openssl rand -hex 2

# Или несколько
for i in {1..4}; do openssl rand -hex 2; done
```

---

## 📊 Оптимизация для РФ (2026)

### Рекомендованные параметры

```json
{
  "realitySettings": {
    "dest": "www.apple.com:443",
    "serverNames": ["apple.com", "icloud.com"],
    "fingerprint": "chrome",  // или "ios" для мобильных
    "shortIds": ["", "2c4d7c0e", "d8b81723"],  // 3-4 shortId
    "maxTimeDiff": 7200,
    "shortIds": ["", "2c4d7c0e", "d8b81723", "0a9b54c5"]
  }
}
```

**Пояснения:**
- `dest: apple.com` — Apple заблокирован в РФ = высокий доверие
- `fingerprint: chrome` — самый распространённый
- `shortIds` — несколько для распределения нагрузки
- `maxTimeDiff: 7200` — допуск часового разбега времени

### Альтернативные dest для fallback

```json
{
  "fallbacks": [
    {
      "dest": "www.microsoft.com:443",
      "serverNames": ["microsoft.com", "windowsupdate.com"]
    },
    {
      "dest": "cdn.cloudflare.com:443",
      "serverNames": ["cloudflare.com"]
    },
    {
      "dest": "www.google.com:443",
      "serverNames": ["google.com", "www.google.com"]
    }
  ]
}
```

---

## 🧪 Тестирование конфигурации

### Проверка подключения

```bash
# Тест с клиента (V2RayNG)
# Импортировать конфиг → Подключиться → Проверить IP

# Проверка fingerprint
curl -vI https://apple.com

# Проверка Routing
curl https://www.google.com/generate_204
```

### Диагностика проблем

| Симптом | Причина | Решение |
|---------|---------|----------|
| Connection refused | Неверный порт/ключ | Проверить конфиг сервера |
| Handshake failure | Неверный fingerprint | Сменить на ios/safari |
| Timeout | Dest блокирован | Сменить dest на fallback |
| Slow connection | Проблемы с flow | Попробовать без flow |

---

## 📋 Чеклист развертывания

- [ ] Сгенерировать ключи (xray x25519)
- [ ] Настроить inbound на порту 443
- [ ] Установить fingerprint: chrome (или ios)
- [ ] Настроить flow: xtls-rprx-vision
- [ ] Добавить 3-4 shortId
- [ ] Настроить dest: apple.com
- [ ] Добавить fallback dest
- [ ] Протестировать с клиента
- [ ] Проверить IP (whatismyipaddress.com)
- [ ] Проверить DNS (нет утечек)

---

## 🔗 Полезные ссылки

- **V2Fly Documentation**: https://xtls.github.io/
- **Reality Config Generator**: https://github.com/XTLS/Reality
- **Fingerprint List**: https://github.com/XTLS/REALITY-check

---

Updated: 2026-02-22
Based on: Инструкция по настройке Xray VLESS-XTLS-Reality3X UI (2024-2025)
Optimized for: RF mobile networks 2026
