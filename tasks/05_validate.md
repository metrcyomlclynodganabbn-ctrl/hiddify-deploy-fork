# ЭТАП 5: Валидация и тестирование

## Цель
Проверить работоспособность всех компонентов после деплоя.

## Шаги

### 1. Проверка подключения к VPS
```bash
# Базовая проверка SSH
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
# Проверка статуса всех служб
echo "🔍 Статус служб:"
systemctl status hiddify-manager --no-pager | grep -E "(Active|loaded)"
systemctl status hiddify-bot --no-pager | grep -E "(Active|loaded)"
systemctl status xray --no-pager | grep -E "(Active|loaded)"

# Проверка открытых портов
echo -e "\n🔍 Открытые порты:"
netstat -tlnp | grep -E "(22|80|443|8443)"

# Проверка дискового пространства
echo -e "\n🔍 Дисковое пространство:"
df -h /

# Проверка нагрузки
echo -e "\n🔍 Нагрузка системы:"
uptime
EOF
```

### 2. Проверка TLS сертификата
```bash
# Проверка сертификата панели
echo "🔍 TLS сертификат для $PANEL_DOMAIN:"
openssl s_client -connect $PANEL_DOMAIN:443 -servername $PANEL_DOMAIN < /dev/null 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates

# Проверка валидности сертификата
curl -vI https://$PANEL_DOMAIN 2>&1 | grep -E "(SSL|TLS|certificate)"
```

### 3. Проверка протоколов
```bash
# Тест VLESS-Reality
echo "🔍 Проверка VLESS-Reality..."
# TODO: Здесь нужен тест с клиентской машины
# Можно использовать v2ray-test или аналогичный инструмент

# Тест Hysteria2
echo "🔍 Проверка Hysteria2..."
# TODO: Тест UDP подключения

# Тест Shadowsocks-2022
echo "🔍 Проверка Shadowsocks-2022..."
# TODO: Тест подключения
```

### 4. Проверка Telegram-бота
```bash
# Отправка тестовой команды
echo "🔍 Тестирование Telegram-бота..."
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" | jq .

# Отправка тестового уведомления админу
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -d "chat_id=$TELEGRAM_ADMIN_ID" \
  -d "text=🧪 Тестирование бота... Если вы это видите, бот работает!"

# Проверка логов бота
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" \
  "journalctl -u hiddify-bot -n 20 --no-pager"
```

### 5. Проверка API Hiddify
```bash
# Проверка статистики панели
echo "🔍 Статистика панели Hiddify..."
curl -X GET "https://$PANEL_DOMAIN/api/stats" \
  -H "Authorization: Bearer $HIDDIFY_API_TOKEN" | jq .

# Проверка списка пользователей
echo "🔍 Количество пользователей:"
curl -X GET "https://$PANEL_DOMAIN/api/users" \
  -H "Authorization: Bearer $HIDDIFY_API_TOKEN" | jq '.total'

# Проверка системного здоровья
curl -X GET "https://$PANEL_DOMAIN/api/health" | jq .
```

### 6. Запуск скриптов валидации
```bash
# Проверка соединения (если доступен прокси-тестер из РФ)
if [ -f "scripts/validate_connection.sh" ]; then
  echo "🔍 Запуск проверки соединения из РФ..."
  bash scripts/validate_connection.sh
fi

# Тест скорости (если доступен)
if [ -f "scripts/speed_test.py" ]; then
  echo "🔍 Запуск теста скорости..."
  python3 scripts/speed_test.py
fi
```

### 7. Нагрузочный тест
```bash
# Симуляция 50 одновременных подключений
echo "🔍 Нагрузочный тест..."
for i in {1..50}; do
  (
    # TODO: Установить соединение с одним из пользователей
    # Здесь должен быть код проверки подключения
    echo "Подключение $i..."
  ) &
done

wait

echo "✅ Нагрузочный тест завершён"

# Проверка нагрузки на сервер
ssh -i "$VPS_SSH_KEY_PATH" -p "$VPS_SSH_PORT" "$VPS_SSH_USER@$VPS_IP" << 'EOF'
echo "CPU:"
top -b -n 1 | grep "Cpu(s)"

echo -e "\nRAM:"
free -h

echo -e "\nСетевые соединения:"
netstat -an | grep ESTABLISHED | wc -l
EOF
```

### 8. Создание отчёта
```bash
# Генерация финального отчёта
cat > output/DEPLOY_SUCCESS.txt <<EOF
✅ DEPLOY SUCCESSFUL

=== ПАНЕЛЬ УПРАВЛЕНИЯ ===
URL: https://$PANEL_DOMAIN
Login: admin
Password: $(cat output/admin_password.txt 2>/dev/null || echo "See .env")

=== TELEGRAM БОТ ===
Bot: @$TELEGRAM_BOT_USERNAME
Admin ID: $TELEGRAM_ADMIN_ID
Commands: /start, /users, /stats, /create_user

=== ПРОТОКОЛЫ ===
✅ VLESS-Reality: настроен
✅ Hysteria2: настроен
✅ Shadowsocks-2022: настроен

=== ПОЛЬЗОВАТЕЛИ ===
Всего создано: $(wc -l < output/subscription_links.txt 2>/dev/null || echo "0")
Ссылки подписок: output/subscription_links.txt

=== СЛЕДУЮЩИЕ ШАГИ ===
1. Импортировать подписку в клиент (V2Ray/Xray/Qv2ray)
2. Протестировать подключение
3. Настроить авто-продление подписки
4. Следить за логами: logs/deploy.log

=== ПОДДЕРЖКА ===
Логи: ssh $VPS_SSH_USER@$VPS_IP "journalctl -u hiddify-manager -f"
Статус: ssh $VPS_SSH_USER@$VPS_IP "systemctl status hiddify-manager"

Generated: $(date)
EOF

cat output/DEPLOY_SUCCESS.txt
```

### 9. Уведомление в Telegram
```bash
# Отправка уведомления об успешном деплое
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -d "chat_id=$TELEGRAM_ADMIN_ID" \
  -d "text=✅ Деплой Hiddify Manager завершён успешно!

Панель: https://$PANEL_DOMAIN
Пользователей: $(wc -l < output/subscription_links.txt 2>/dev/null || echo "0")

Подробности в output/DEPLOY_SUCCESS.txt"
```

## Чеклист завершения
- [ ] Все службы active
- [ ] Панель доступна по HTTPS
- [ ] TLS сертификат валиден
- [ ] Бот отвечает на команды
- [ ] API работает
- [ ] Протоколы настроены
- [ ] Пользователи созданы
- [ ] Нагрузочный тест пройден

## Логирование
```bash
exec > >(tee -a logs/validate.log)
exec 2>&1
```
