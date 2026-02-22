# ЭТАП 0: Инициализация окружения

## Цель
Проверить предварительные условия и подготовить окружение для деплоя.

## Шаги

### 1. Валидация .env
```bash
# Загрузить переменные
source .env

# Проверить обязательные поля
required_vars=(
  "VPS_IP"
  "VPS_SSH_USER"
  "VPS_SSH_KEY_PATH"
  "PANEL_DOMAIN"
  "TELEGRAM_BOT_TOKEN"
  "TELEGRAM_ADMIN_ID"
)

for var in "${required_vars[@]}"; do
  if [[ -z "${!var}" ]] || [[ "${!var}" == "your."* ]]; then
    echo "❌ ОШИБКА: $var не заполнен в .env"
    exit 1
  fi
done

echo "✅ Все обязательные переменные заполнены"
```

### 2. Проверка SSH-доступа
```bash
# Пробное подключение
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" \
  -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=no \
  "$VPS_SSH_USER@$VPS_IP" \
  "uname -a && free -h && nproc"

# Ожидаемый вывод:
# Linux <hostname> 5.15.0-generic #... Ubuntu 22.04
# Mem: 4.0G
# 2
```

### 3. Проверка системных требований
```bash
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Проверка ОС
if ! grep -q "Ubuntu 22.04" /etc/os-release; then
  echo "⚠️  ВНИМАНИЕ: ОС не Ubuntu 22.04. Продолжаем на свой риск."
fi

# Проверка RAM (минимум 4GB)
total_mem=$(free -m | awk '/^Mem:/{print $2}')
if [ "$total_mem" -lt 4096 ]; then
  echo "❌ ОШИБКА: Недостаточно RAM (${total_mem}MB < 4096MB)"
  exit 1
fi

# Проверка CPU (минимум 2 ядра)
cpu_cores=$(nproc)
if [ "$cpu_cores" -lt 2 ]; then
  echo "❌ ОШИБКА: Недостаточно CPU cores (${cpu_cores} < 2)"
  exit 1
fi

# Проверка дискового пространства (минимум 20GB)
disk_free=$(df -BG / | awk 'NR==2 {print $4}')
if [ "$disk_free" -lt 20 ]; then
  echo "❌ ОШИБКА: Недостаточно дискового пространства (${disk_free}GB < 20GB)"
  exit 1
fi

echo "✅ Системные требования выполнены:"
echo "   - OS: $(cat /etc/os-release | grep PRETTY_NAME)"
echo "   - RAM: ${total_mem}MB"
echo "   - CPU: ${cpu_cores} cores"
echo "   - Disk: ${disk_free}GB free"
EOF
```

### 4. Установка локальных утилит (на macOS)
```bash
# Проверить наличие jq
if ! command -v jq &> /dev/null; then
  echo "Установка jq..."
  brew install jq
fi

# Проверить наличие yq (для YAML)
if ! command -v yq &> /dev/null; then
  echo "Установка yq..."
  brew install yq
fi

# Проверить наличие openssh-client
if ! command -v ssh &> /dev/null; then
  echo "❌ ОШИБКА: SSH не найден"
  exit 1
fi

echo "✅ Локальные утилиты готовы"
```

## Критерии завершения
- ✅ Все переменные .env валидны
- ✅ SSH-подключение работает
- ✅ VPS соответствует требованиям: Ubuntu 22.04, 4GB+ RAM, 2+ vCPU, 20GB+ disk
- ✅ Локальные утилиты установлены

## Логирование
Все шаги логировать в `logs/init.log`:
```bash
exec > >(tee -a logs/init.log)
exec 2>&1
```
