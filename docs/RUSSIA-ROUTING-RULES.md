# Russia Routing Rules для 3X-UI

Автоматически обновляемые правила маршрутизации на основе заблокированных доменов и IP-адресов в России.

## Источники

### Основные репозитории

| Репозиторий | Описание | Обновление |
|-------------|----------|------------|
| [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat) | Официальный источник для v2rayN | Каждые 6 часов |
| [runetfreedom/russia-blocked-geoip](https://github.com/runetfreedom/russia-blocked-geoip) | Генерация geoip файлов | Автоматически |
| [runetfreedom/russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite) | Генерация geosite файлов | Автоматически |

### Источники данных

**geoip.dat:**
- **ru-blocked** — ipresolve.lst и subnet.lst (antifilter.download)
- **ru-blocked-community** — community.lst (community.antifilter.download)
- **re-filter** — ipsum.lst (re:filter)

**geosite.dat:**
- Все категории из @v2fly/domain-list-community
- **geosite:ru-blocked** — заблокированные домены
- **geosite:ru-blocked-all** — все заблокированные (700K+, с осторожностью!)
- **geosite:antifilter-download** — ~700K доменов
- **geosite:antifilter-download-community** — community список
- **geosite:refilter** — re:filter домены

---

## Скачать файлы

### Последняя версия

```bash
# geoip.dat
wget https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat

# geosite.dat
wget https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat
```

### Прямые ссылки

- **geoip.dat:** https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat
- **geosite.dat:** https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat

---

## Категории GeoIP

| Категория | Описание |
|-----------|----------|
| `geoip:ru-blocked` | Заблокированные IP (antifilter + subnet) |
| `geoip:ru-blocked-community` | Community список заблокированных IP |
| `geoip:re-filter` | IP от re:filter |
| `geoip:cloudflare` | Cloudflare CDN |
| `geoip:cloudfront` | AWS CloudFront |
| `geoip:facebook` | Facebook/Meta сервисы |
| `geoip:fastly` | Fastly CDN |
| `geoip:google` | Google сервисы |
| `geoip:netflix` | Netflix |
| `geoip:telegram` | Telegram |
| `geoip:twitter` | Twitter/X |
| `geoip:ddos-guard` | DDOS-GUARD |
| `geoip:yandex` | Yandex сервисы |

---

## Категории GeoSite

### Заблокированные в РФ

| Категория | Доменов | Описание |
|-----------|---------|----------|
| `geosite:ru-blocked` | ~100K | Заблокированные домены |
| `geosite:ru-blocked-all` | ~700K+ ⚠️ | Все заблокированные (с осторожностью!) |
| `geosite:antifilter-download` | ~700K ⚠️ | antifilter.download |
| `geosite:antifilter-download-community` | ~50K | community.antifilter |
| `geosite:refilter` | ~30K | re:filter |

### Сервисы и платформы

| Категория | Описание |
|-----------|----------|
| `geosite:google` | Google (поиск, YouTube, Gmail) |
| `geosite:youtube` | YouTube |
| `geosite:discord` | Discord |
| `geosite:twitter` | Twitter/X |
| `geosite:meta` | Facebook, Instagram |
| `geosite:openai` | OpenAI (ChatGPT) |
| `geosite:telegram` | Telegram |
| `geosite:netflix` | Netflix |
| `geosite:spotify` | Spotify |

### Реклама и телеметрия

| Категория | Описание |
|-----------|----------|
| `geosite:category-ads-all` | Вся реклама |
| `geosite:win-spy` | Телеметрия Windows |
| `geosite:win-update` | Обновления Windows |
| `geosite:win-extra` | Прочие сервисы Windows |

---

## Установка в 3X-UI

### Шаг 1: Скачивание файлов

```bash
# Перейдите в директорию Xray
cd /usr/local/x-ui/bin/

# Или в директорию data
cd /etc/x-ui/

# Скачайте файлы
wget -O geoip.dat https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat
wget -O geosite.dat https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat
```

### Шаг 2: Настройка маршрутизации

В панели 3X-UI:
```
Xray Configs → Routing Rules
```

#### Рекомендуемая конфигурация

```json
{
  "domainStrategy": "AsIs",
  "rules": [
    {
      "type": "field",
      "outboundTag": "direct",
      "domain": ["geosite:private"]
    },
    {
      "type": "field",
      "outboundTag": "proxy",
      "domain": [
        "geosite:ru-blocked",
        "geosite:antifilter-download-community",
        "geosite:refilter",
        "geosite:google",
        "geosite:youtube",
        "geosite:discord",
        "geosite:twitter",
        "geosite:meta",
        "geosite:openai",
        "geosite:telegram"
      ]
    },
    {
      "type": "field",
      "outboundTag": "proxy",
      "ip": [
        "geoip:ru-blocked",
        "geoip:ru-blocked-community"
      ]
    },
    {
      "type": "field",
      "outboundTag": "direct",
      "network": "udp,tcp"
    }
  ]
}
```

#### Блокировка рекламы

```json
{
  "rules": [
    {
      "type": "field",
      "outboundTag": "block",
      "domain": [
        "geosite:category-ads-all",
        "geosite:win-spy"
      ]
    }
  ]
}
```

### Шаг 3: Применение

1. Сохраните конфигурацию в панели
2. Перезапустите Xray:
   ```bash
   systemctl restart 3x-ui
   ```

---

## Скрипт автоматического обновления

```bash
#!/bin/bash
# update-russia-rules.sh

XUI_DIR="/etc/x-ui"
BACKUP_DIR="$XUI_DIR/backup"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

echo "🔄 Обновление российских правил маршрутизации..."

# Бэкап текущих файлов
echo "💾 Создание резервной копии..."
cp $XUI_DIR/geoip.dat $BACKUP_DIR/geoip.dat.$DATE
cp $XUI_DIR/geosite.dat $BACKUP_DIR/geosite.dat.$DATE

# Скачивание новых версий
echo "⬇️  Загрузка новых версий..."
cd $XUI_DIR

wget -q --show-progress -O geoip.dat \
  https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat

wget -q --show-progress -O geosite.dat \
  https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat

if [ $? -eq 0 ]; then
    echo "✅ Файлы успешно загружены"
    
    # Перезапуск службы
    echo "🔄 Перезапуск службы..."
    systemctl restart 3x-ui
    
    echo "✅ Правила обновлены!"
else
    echo "❌ Ошибка загрузки файлов"
    exit 1
fi
```

### Использование

```bash
# Сделать исполняемым
chmod +x update-russia-rules.sh

# Запустить
./update-russia-rules.sh
```

### По расписанию (cron)

```bash
# Редактирование crontab
crontab -e

# Обновление каждые 6 часов
0 */6 * * * /root/update-russia-rules.sh
```

---

## Рекомендации

### ⚠️ Важные предупреждения

1. **geosite:ru-blocked-all** содержит 700K+ доменов — может замедлить работу
2. **geosite:antifilter-download** содержит ~700K доменов — используйте с осторожностью
3. Рекомендуется использовать **geosite:ru-blocked** + **geosite:antifilter-download-community**

### Оптимальная конфигурация

Для большинства пользователей:

```
Домены для proxy:
- geosite:ru-blocked
- geosite:antifilter-download-community
- geosite:refilter
- geosite:google
- geosite:youtube
- geosite:discord
- geosite:telegram

IP для proxy:
- geoip:ru-blocked
- geoip:ru-blocked-community
```

### Блокировка рекламы

```
Домены для block:
- geosite:category-ads-all
- geosite:win-spy
```

---

## Использование в клиентах

### v2rayN / v2rayNG

1. Поместите файлы в папку с программой
2. В настройках укажите пути к файлам
3. Используйте в правилах маршрутизации

### Clash / Mihomo

```yaml
geodata-mode: true
geox-url:
  geoip: "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat"
  geosite: "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat"
```

### Sing-box

```bash
# Конвертация в srs формат
python3 geodat2srs.py geoip.dat geosite.dat
```

---

## Смежные проекты

| Проект | Описание |
|--------|----------|
| [@runetfreedom/russia-blocked-geoip](https://github.com/runetfreedom/russia-blocked-geoip) | Генерация geoip файлов |
| [@runetfreedom/russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite) | Генерация geosite файлов |
| [@runetfreedom/russia-v2ray-custom-routing-list](https://github.com/runetfreedom/russia-v2ray-custom-routing-list) | Правила для клиентов |
| [@runetfreedom/geodat2srs](https://github.com/runetfreedom/geodat2srs) | Конвертер в sing-box srs |
| [@Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) | Оригинальный проект |

---

## Благодарности

- **antifilter.download** — данные о заблокированных доменах
- **re:filter** — отфильтрованные данные
- **@Loyalsoldier** — идея и основа проекта
- **@v2fly** — domain-list-community

---

## Поддержка

- GitHub Issues: https://github.com/runetfreedom/russia-v2ray-rules-dat/issues
- Telegram: @runetfreedom
