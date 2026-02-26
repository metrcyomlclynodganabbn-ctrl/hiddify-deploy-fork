#!/bin/bash
# Quick update for monitor_bot.py - VLESS URL generation

BOT_FILE="/opt/hiddify-manager/scripts/monitor_bot.py"
BACKUP_FILE="/opt/hiddify-manager/scripts/monitor_bot.py.backup"

echo "🔄 Updating Telegram bot with VLESS URL generation..."

# Backup original file
cp "$BOT_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

# Add VLESS generation functions after imports
python3 << 'PYEOF'
import re

# Read original file
with open('/opt/hiddify-manager/scripts/monitor_bot.py', 'r') as f:
    content = f.read()

# Add VLESS functions after existing imports (before БАЗА ДАННЫХ)
vless_functions = '''
# ============================================================================
# VLESS URL ГЕНЕРАТОР
# ============================================================================

def generate_vless_url(user_uuid: str, server_ip: str, port: int,
                        public_key: str, sni: str = "www.apple.com",
                        flow: str = "xtls-rprx-vision", label: str = "SKRT-VPN") -> str:
    """Генерирует VLESS-Reality URL для импорта в клиент"""
    base = f"vless://{user_uuid}@{server_ip}:{port}"
    params = [
        "encryption=none",
        f"flow={flow}",
        "security=reality",
        f"sni={sni}",
        "fp=chrome",
        f"pbk={public_key}",
        "type=tcp",
        "header=none"
    ]
    url = f"{base}?{'&'.join(params)}#{label}"
    return url


def generate_vless_qr(url: str):
    """Генерирует QR код для VLESS URL"""
    try:
        import qrcode
        import tempfile
        from io import BytesIO

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(temp_file, format='PNG')
        temp_file.close()

        return temp_file.name
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        return None


'''

# Find location to insert (before "# ============================================================================
# БАЗА ДАННЫХ")
insert_marker = "# ============================================================================\n# БАЗА ДАННЫХ"

if insert_marker in content and 'generate_vless_url' not in content:
    content = content.replace(insert_marker, vless_functions + insert_marker)
    print("✅ VLESS functions added")
else:
    print("⚠️  VLESS functions already exist or marker not found")

# Write updated file
with open('/opt/hiddify-manager/scripts/monitor_bot.py', 'w') as f:
    f.write(content)

print("✅ Bot file updated")
PYEOF

echo ""
echo "✅ Update completed!"
echo "🔄 Restarting bot..."
systemctl restart hiddify-bot
sleep 2
systemctl status hiddify-bot --no-pager | head -10

echo ""
echo "📋 Test the bot:"
echo "   1. Open @SKRTvpnbot"
echo "   2. Press '🔗 Получить ключ'"
echo "   3. Select 'VLESS-Reality ⭐'"
echo "   4. You should receive VLESS URL + QR code"
