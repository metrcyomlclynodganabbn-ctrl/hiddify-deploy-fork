#!/bin/bash
# Update handle_protocol_selection function in monitor_bot.py

BOT_FILE="/opt/hiddify-manager/scripts/monitor_bot.py"

echo "🔄 Updating protocol handler with VLESS URL generation..."

python3 << 'PYEOF'
import re

# Read file
with open('/opt/hiddify-manager/scripts/monitor_bot.py', 'r') as f:
    content = f.read()

# New handler function
new_handler = '''@bot.callback_query_handler(func=lambda call: call.data.startswith('protocol_'))
def handle_protocol_selection(call):
    """Обработка выбора протокола"""

    telegram_id = call.message.chat.id
    protocol = call.data.split('_')[1]

    user = get_user(telegram_id)

    if not user:
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return

    # Получаем параметры из .env
    vps_ip = os.getenv('VPS_IP', '5.45.114.73')
    reality_public_key = os.getenv('REALITY_PUBLIC_KEY', '')
    reality_sni = os.getenv('REALITY_SNI', 'www.apple.com')
    vless_port = int(os.getenv('VLESS_PORT', '443'))

    if protocol == 'vless':
        # Используем UUID пользователя или генерируем
        user_uuid = user.get('vless_uuid') or str(uuid.uuid4())

        # Генерируем VLESS URL
        vless_url = generate_vless_url(
            user_uuid=user_uuid,
            server_ip=vps_ip,
            port=vless_port,
            public_key=reality_public_key,
            sni=reality_sni,
            label=f"SKRT-VPN-{user['telegram_first_name']}"
        )

        config_name = "VLESS-Reality ⭐"

        # Отправляем текстовый URL
        bot.send_message(
            telegram_id,
            f"📋 *{config_name}*\n\\n"
            f"```\\n{vless_url}\\n```\\n\\n"
            f"📱 *Инструкция:*\\n"
            f"1. Скопируйте ссылку выше\\n"
            f"2. Откройте Nekobox/V2Ray\\n"
            f"3. Импорт из буфера обмена\\n"
            f"4. Подключитесь",
            parse_mode='Markdown'
        )

        # Генерируем и отправляем QR код
        qr_file = generate_vless_qr(vless_url)
        if qr_file:
            try:
                with open(qr_file, 'rb') as qr:
                    bot.send_photo(
                        telegram_id,
                        qr,
                        caption="📷 *Отсканируйте QR код* для быстрого импорта",
                        parse_mode='Markdown'
                    )
                # Удаляем временный файл
                os.unlink(qr_file)
            except Exception as e:
                logger.error(f"QR code error: {e}")

    elif protocol == 'hysteria2':
        # TODO: Реализовать Hysteria2
        config_link = f"hysteria2://{user['hysteria2_password']}@{vps_ip}:443/?sni={reality_sni}"
        config_name = "Hysteria2 🚀"

        bot.send_message(
            telegram_id,
            f"📋 *{config_name}*\\n\\n"
            f"```\\n{config_link}\\n```\\n\\n"
            f"Протокол в разработке",
            parse_mode='Markdown'
        )
    else:
        # TODO: Реализовать SS-2022
        config_link = f"ss2022://{user['ss2022_password']}@{vps_ip}:8388"
        config_name = "Shadowsocks-2022 🔒"

        bot.send_message(
            telegram_id,
            f"📋 *{config_name}*\\n\\n"
            f"```\\n{config_link}\\n```\\n\\n"
            f"Протокол в разработке",
            parse_mode='Markdown'
        )

    bot.answer_callback_query(call.id, "Конфигурация отправлена")'''

# Pattern to find old handler
old_handler_pattern = r"@bot\.callback_query_handler\(func=lambda call: call\.data\.startswith\('protocol_'\)\)\s*def handle_protocol_selection\(call\):.*?bot\.answer_callback_query\(call\.id, \"Конфигурация отправлена\"\)"

# Replace
new_content = re.sub(old_handler_pattern, new_handler, content, flags=re.DOTALL)

# Check if replacement happened
if new_content != content:
    with open('/opt/hiddify-manager/scripts/monitor_bot.py', 'w') as f:
        f.write(new_content)
    print("✅ Protocol handler updated")
else:
    print("⚠️  Handler pattern not found, trying alternative...")

    # Alternative: find by line numbers and replace section
    lines = content.split('\n')
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if '@bot.callback_query_handler(func=lambda call: call.data.startswith' in line and 'protocol_' in line:
            start_idx = i
        if start_idx and i > start_idx and 'bot.answer_callback_query(call.id, "Конфигурация отправлена")' in line:
            end_idx = i + 1
            break

    if start_idx and end_idx:
        # Replace the section
        new_lines = lines[:start_idx] + [new_handler] + lines[end_idx:]
        new_content = '\n'.join(new_lines)

        with open('/opt/hiddify-manager/scripts/monitor_bot.py', 'w') as f:
            f.write(new_content)
        print("✅ Protocol handler updated (alternative method)")
    else:
        print("❌ Could not find handler to replace")
        print(f"Start: {start_idx}, End: {end_idx}")

PYEOF

echo ""
echo "🔄 Restarting bot..."
systemctl restart hiddify-bot
sleep 2

echo ""
echo "✅ Update complete!"
echo "📋 Check logs:"
echo "   journalctl -u hiddify-bot -n 20"
