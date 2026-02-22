# Routing Rules Configuration
# На основе v2fly/domain-list-community и Iran-v2ray-rules

## Overview

Этот проект интегрирует community-правила для маршрутизации трафика:
- **v2fly/domain-list-community** — основные категории доменов
- **Iran-v2ray-rules** — оптимизированные правила для РФ/Иран

---

## 📦 Загрузка готовых правил

### GitHub Releases (рекомендуется)

```bash
# V2Fly Domain List Community
wget https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat -O /etc/xray/geosite.dat

# Iran v2ray Rules (оптимизировано для цензуры)
wget https://raw.githubusercontent.com/Chocolate4U/Iran-v2ray-rules/release/geosite.dat -O /etc/xray/geosite-iran.dat
wget https://raw.githubusercontent.com/Chocolate4U/Iran-v2ray-rules/release/geoip.dat -O /etc/xray/geoip-iran.dat
```

### Lite версии (для мобильных)

```bash
# Меньший размер, быстрее загрузка
wget https://raw.githubusercontent.com/Chocolate4U/Iran-v2ray-rules/release/geosite-lite.dat -O /etc/xray/geosite.dat
wget https://raw.githubusercontent.com/Chocolate4U/Iran-v2ray-rules/release/geoip-lite.dat -O /etc/xray/geoip.dat
```

---

## 🔧 Применение в конфиге Xray

### Базовая маршрутизация

```json
{
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "outboundTag": "block",
        "domain": [
          "geosite:category-ads-all",
          "geosite:malware",
          "geosite:phishing",
          "geosite:cryptominers"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "domain": [
          "geosite:ru",
          "geosite:private"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "ip": [
          "geoip:ru",
          "geoip:private"
        ]
      },
      {
        "type": "field",
        "outboundTag": "proxy",
        "domain": [
          "geosite:category-anticensorship",
          "geosite:category-media",
          "geosite:category-vpnservices",
          "geosite:geolocation-!cn",
          "geosite:geolocation-!ru"
        ]
      },
      {
        "type": "field",
        "outboundTag": "proxy",
        "ip": [
          "geoip:geolocation-!cn",
          "geoip:geolocation-!ru"
        ]
      }
    ]
  }
}
```

### Расширенная маршрутизация (с Iran rules)

```json
{
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      {
        "type": "field",
        "outboundTag": "block",
        "domain": [
          "geosite:category-ads-all",
          "geosite:malware",
          "geosite:phishing",
          "geosite:cryptominers",
          "geosite:nsfw"
        ]
      },
      {
        "type": "field",
        "outboundTag": "block",
        "ip": [
          "geoip:malware",
          "geoip:phishing"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "domain": [
          "geosite:ru",
          "geosite:category-bank",  // Банки РФ
          "geosite:category-gov"    // Правительство РФ
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "ip": [
          "geoip:ru",
          "geoip:private"
        ]
      },
      {
        "type": "field",
        "outboundTag": "proxy",
        "domain": [
          "geosite:category-anticensorship",
          "geosite:category-media",
          "geosite:category-vpnservices",
          "geosite:geolocation-!ru",
          "geosite:social",           // Соцсети
          "geosite:google",           // Google сервисы
          "geosite:github",           // GitHub
          "geosite:telegram"           // Telegram
        ]
      },
      {
        "type": "field",
        "outboundTag": "proxy",
        "ip": [
          "geoip:geolocation-!ru"
        ]
      }
    ]
  }
}
```

---

## 📋 Доступные категории

### из v2fly/domain-list-community

**Блокировка:**
- `geosite:category-ads-all` — вся реклама
- `geosite:category-porn` — контент для взрослых
- `geosite:malware` — вредоносное ПО
- `geosite:phishing` — фишинг
- `geosite:cryptominers` — криптомайнеры

**Прямое соединение:**
- `geosite:cn` — Китай
- `geosite:private` — локальные сети
- `geosite:ru` — Россия (если добавлена)

**Прокси:**
- `geosite:category-anticensorship` — антицензура
- `geosite:category-media` — медиа сервисы
- `geosite:category-vpnservices` — VPN сервисы
- `geosite:geolocation-!cn` — всё кроме Китая
- `geosite:geolocation-!ru` — всё кроме России

### из Iran-v2ray-rules (дополнительно)

**Иран-специфичные (адаптировано для РФ):**
- `geosite:ir` → адаптировать под `geosite:ru`
- `geosite:category-ir` → `geosite:category-ru`
- `geosite:social` — соцсети (Facebook, Instagram, Twitter, TikTok, Telegram)
- `geosite:nsfw` — взрослый контент
- `geosite:sanctioned` — санкционные ресурсы

**CDN и сервисы:**
- `geoip:cloudflare` — Cloudflare CDN
- `geoip:cloudfront` — AWS CloudFront
- `geoip:fastly` — Fastly CDN
- `geoip:google` — Google сервисы
- `geoip:amazon` — Amazon/AWS
- `geoip:microsoft` — Microsoft/Azure
- `geoip:telegram` — Telegram
- `geoip:github` — GitHub
- `geoip:openai` — ChatGPT/OpenAI
- `geoip:netflix` — Netflix
- `geoip:facebook` — Meta (Facebook, Instagram, WhatsApp)
- `geoip:twitter` — X (Twitter)

---

## 🎯 Рекомендации для РФ (2026)

### Приоритеты блокировки

```json
{
  "type": "field",
  "outboundTag": "block",
  "domain": [
    "geosite:category-ads-all",  // Реклама
    "geosite:malware",           // Вредоносное ПО
    "geosite:phishing",          // Фишинг
    "geosite:cryptominers"       // Криптомайнеры
  ]
}
```

### Прямое соединение (RF)

```json
{
  "type": "field",
  "outboundTag": "direct",
  "domain": [
    "geosite:ru",              // Российские домены
    "geosite:category-bank",    // Банки
    "geosite:category-gov",     // Правительство
    "geosite:yandex",           // Яндекс (если есть)
    "geosite:vk"                // ВКонтакте (если есть)
  ],
  "ip": [
    "geoip:ru",                // Российские IP
    "geoip:private"            // Локальные сети
  ]
}
```

### Прокси (все остальное)

```json
{
  "type": "field",
  "outboundTag": "proxy",
  "domain": [
    "geosite:category-anticensorship",  // Антицензура
    "geosite:category-media",           // Медиа
    "geosite:social",                   // Соцсети
    "geosite:google",                   // Google
    "geosite:github",                   // GitHub
    "geosite:telegram",                 // Telegram
    "geosite:geolocation-!ru"           // Всё кроме РФ
  ],
  "ip": [
    "geoip:geolocation-!ru"            // Все IP кроме РФ
  ]
}
```

---

## 🔨 Генерация своих правил

### Клонирование и модификация

```bash
# Клонировать репозиторий
git clone https://github.com/v2fly/domain-list-community.git
cd domain-list-community

# Добавить свои правила
echo "domain:example.com @custom" >> data/custom

# Сгенерировать dlc.dat
go run ./ --datapath=./data

# Скопировать
cp dlc.dat /etc/xray/
```

### Добавление российских доменов

```bash
# Создать список российских доменов
cat > data/ru-services <<'EOF'
# Яндекс
domain:yandex.ru @ru
domain:yandex.net @ru
domain:yandex.com @ru
full:yandex.ru @ru

# ВКонтакте
domain:vk.com @ru
domain:vkontakte.ru @ru

# Mail.ru
domain:mail.ru @ru
EOF

# Сгенерировать
go run ./ --datapath=./data
```

---

## 📚 Полезные ресурсы

- **V2Fly Domain List**: https://github.com/v2fly/domain-list-community
- **Iran v2ray Rules**: https://github.com/Chocolate4U/Iran-v2ray-rules
- **Iran Hosted Domains**: https://github.com/bootmortis/iran-hosted-domains (для RF: домены в зоне РФ)
- **PersianBlocker**: https://github.com/MasterKia/PersianBlocker (реклама)

---

## ⚠️ Важные замечания

1. **Обновление**: Правила обновляются регулярно. Настоятельно рекомендуется автоматизировать обновление через cron.

2. **Lite версии**: Для мобильных клиентов используйте lite-версии для уменьшения размера.

3. **RU-специфика**: Адаптируйте иранские правила под российскую реальность (замените ir→ru, добавьте яндекс/вк/autres).

4. **Security**: Регулярно обновляйте списки malware и phishing.

---

Updated: 2026-02-22
Based on: v2fly/domain-list-community & Iran-v2ray-rules
Optimized for: RF censorship environment
