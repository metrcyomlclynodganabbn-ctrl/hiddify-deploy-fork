# ЭТАП 1: Установка Hiddify Manager v8

## Цель
Установить Hiddify Manager v8 на VPS и настроить базовую конфигурацию.

## Шаги

### 1. Подготовка VPS
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Обновление системы
apt update && apt upgrade -y

# Установка зависимостей
apt install -y \
  curl \
  wget \
  python3-pip \
  python3-venv \
  git \
  ufw \
  fail2ban

# Настройка firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "✅ VPS подготовлен"
EOF
```

### 2. Установка Hiddify Manager v8
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Скачивание и запуск установщика
export INSTALLER_URL="https://i.hiddify.com/v8.99.0"

echo "🚀 Запуск установки Hiddify Manager v8..."
bash <(curl -sL "$INSTALLER_URL")

echo "✅ Установка завершена"
EOF
```

### 3. Сохранение учётных данных
```bash
# Получить временный пароль из вывода установщика
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "cat /opt/hiddify-manager/config/admin_secret.txt" \
  > output/admin_password.txt

ADMIN_PASS=$(cat output/admin_password.txt)

echo "📝 Учётные данные сохранены в output/admin_password.txt"
echo "   URL: https://$PANEL_DOMAIN"
echo "   Login: admin"
echo "   Password: $ADMIN_PASS"
```

### 4. Проверка статуса служб
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Проверка статуса Hiddify
systemctl status hiddify-manager --no-pager

# Проверка открытых портов
netstat -tlnp | grep -E "(80|443|22)"

# Проверка дискового пространства
df -h /

echo "✅ Службы работают корректно"
EOF
```

## Критерии завершения
- ✅ Hiddify Manager v8 установлен
- ✅ Панель доступна по HTTPS
- ✅ Учётные данные сохранены
- ✅ Все службы в статусе active

## Troubleshooting

### Если установка зависла
```bash
# Проверить логи
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "journalctl -u hiddify-manager -f"

# Перезапустить установку с флагом --force
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "rm -rf /opt/hiddify-manager && bash <(curl -sL https://i.hiddify.com/v8.99.0) --force"
```

### Если панель не доступна
```bash
# Проверить DNS
nslookup $PANEL_DOMAIN

# Проверить сертификат TLS
curl -vI https://$PANEL_DOMAIN

# Проверить firewall
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "ufw status verbose"
```

## Логирование
```bash
exec > >(tee -a logs/install.log)
exec 2>&1
```
