# ЭТАП 2: Настройка протоколов (RU-оптимизация)

## Цель
Настроить протоколы VLESS-Reality, Hysteria2, Shadowsocks-2022 с оптимизацией для работы в РФ.

## Шаги

### 1. Генерация ключей для REALITY
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Установка Xray
bash <(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)

# Генерация ключей
xray x25519 > /tmp/reality_keys.txt 2>&1

# Извлечение публичного и приватного ключей
PRIVATE_KEY=$(grep "Private key" /tmp/reality_keys.txt | awk '{print $3}')
PUBLIC_KEY=$(grep "Public key" /tmp/reality_keys.txt | awk '{print $3}')

echo "REALITY_PRIVATE_KEY=$PRIVATE_KEY" >> /opt/hiddify-manager/config/.env
echo "REALITY_PUBLIC_KEY=$PUBLIC_KEY" >> /opt/hiddify-manager/config/.env

cat /tmp/reality_keys.txt
EOF

# Скопировать ключи локально
scp -i "$VPS_SSH_KEY_PATH" -P "$VPS_SSH_PORT" \
  "$VPS_SSH_USER@$VPS_IP:/tmp/reality_keys.txt" \
  output/reality_keys.txt
```

### 2. Настройка VLESS-Reality (приоритетный протокол)
```bash
# Создание конфигурации Reality
REALITY_CONFIG=$(cat <<EOF
{
  "protocol": "vless",
  "settings": {
    "vnext": [
      {
        "address": "$PANEL_DOMAIN",
        "port": 443,
        "users": [
          {
            "id": "$(uuidgen)",
            "flow": "xtls-rprx-vision",
            "encryption": "none"
          }
        ]
      }
    ]
  },
  "streamSettings": {
    "network": "tcp",
    "security": "reality",
    "realitySettings": {
      "dest": "$REALITY_DEST",
      "serverNames": $REALITY_SNI_LIST,
      "privateKey": "$REALITY_PRIVATE_KEY",
      "shortIds": [""],
      "fingerprint": "chrome"
    }
  }
}
EOF
)

# Применить конфигурацию через API Hiddify
# (детали API зависят от версии Hiddify)
echo "$REALITY_CONFIG" > output/vless_reality_config.json
```

### 3. Настройка Hysteria2
```bash
# Загрузка пресетов Hysteria2
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Создание директории для конфигов Hysteria2
mkdir -p /opt/hiddify-manager/config/hysteria2

# Копирование пресетов
cat > /opt/hiddify-manager/config/hysteria2/config.yaml <<'HYSTERIA_CONFIG'
# Optimized for Russian mobile networks
listen: :443
tls:
  cert: /opt/hiddify-manager/config/tls.crt
  key: /opt/hiddify-manager/config/tls.key

auth:
  type: userpass
  userpass:
    "user1": "pass1"

masquerade:
  type: proxy
  proxy:
    url: https://www.apple.com
    rewriteHost: true

transport:
  udp:
    udpMTU: 1250
  congestionControl: brutal
  upMbps: 100
  downMbps: 100

QUIC:
  initStreamReceiveWindow: 8388608
  maxStreamReceiveWindow: 8388608
  initConnReceiveWindow: 20971520
  maxConnReceiveWindow: 20971520
  maxIdleTimeout: 30s
  keepAlivePeriod: 10s
HYSTERIA_CONFIG

echo "✅ Hysteria2 настроен"
EOF
```

### 4. Настройка Shadowsocks-2022 (резервный протокол)
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Создание конфигурации SS-2022
cat > /opt/hiddify-manager/config/shadowsocks2022.json <<'SS2022_CONFIG'
{
  "method": "2022-blake3-aes-256-gcm",
  "password": "$(openssl rand -base64 32)",
  "network": "tcp,udp",
  "plugin": "v2ray-plugin",
  "plugin_opts": "tls;host=$PANEL_DOMAIN"
}
SS2022_CONFIG

echo "✅ Shadowsocks-2022 настроен"
EOF
```

### 5. Проверка протоколов
```bash
# Тест VLESS-Reality
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Проверка, что порты открыты
netstat -tlnp | grep -E "(443|8443)"

# Проверка статуса Xray
systemctl status xray --no-pager

# Проверка конфигурации
xray -test -config /opt/hiddify-manager/config/vless_reality.json
EOF
```

## RU-специфичные оптимизации

### REALITY Anti-Detection
```bash
# Настройка fingerprint для минимизации детекта
# Использовать "chrome" или "ios" fingerprint
echo "REALITY_FINGERPRINT=chrome" >> .env
```

### Hysteria2 для мобильных сетей
```bash
# Включить Brutal congestion control для стабилизации скорости
# на нестабильных мобильных соединениях
cat > output/hysteria2_mobile.yaml <<EOF
congestionControl: brutal
upMbps: 50
downMbps: 50
QUIC:
  maxIdleTimeout: 60s
  keepAlivePeriod: 20s
EOF
```

## Критерии завершения
- ✅ VLESS-Reality настроен и работает
- ✅ Hysteria2 настроен и работает
- ✅ Shadowsocks-2022 настроен как резервный
- ✅ Все порты открыты и доступны
- ✅ Конфигурации сохранены в `output/`

## Логирование
```bash
exec > >(tee -a logs/protocols.log)
exec 2>&1
```
