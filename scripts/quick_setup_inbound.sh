#!/bin/bash
# Quick setup VLESS-Reality inbound for 3X-ui

echo "🚀 Setting up VLESS-Reality inbound..."

# Generate keys
KEYS=$(/usr/local/x-ui/bin/xray-linux-amd64 x25519)

PRIVATE_KEY=$(echo "$KEYS" | grep "Private key" | cut -d' ' -f3)
PUBLIC_KEY=$(echo "$KEYS" | grep "Public key" | cut -d' ' -f3)
UUID=$(cat /proc/sys/kernel/random/uuid)

echo "✅ Keys generated:"
echo "   Private: $PRIVATE_KEY"
echo "   Public: $PUBLIC_KEY"
echo "   UUID: $UUID"

# Save to file for reference
cat > /opt/hiddify-manager/config/vless_keys.txt << EOF
VLESS-Reality Configuration
==========================
Server: 5.45.114.73
Port: 443
UUID: $UUID
Public Key: $PUBLIC_KEY
Private Key: $PRIVATE_KEY
SNI: www.apple.com
Flow: xtls-rprx-vision

VLESS URL:
vless://${UUID}@5.45.114.73:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.apple.com&fp=chrome&pbk=${PUBLIC_KEY}&type=tcp#SKRT-VPN
EOF

echo "✅ Configuration saved to /opt/hiddify-manager/config/vless_keys.txt"
cat /opt/hiddify-manager/config/vless_keys.txt

echo ""
echo "📋 Next: Add this inbound through 3X-ui web panel:"
echo "   URL: https://5.45.114.73:2053/XMWc515djPCq2ohc11/"
echo "   Login: admin / T7QC9oj8gx4FxyB9"
echo ""
echo "   Inbound Settings:"
echo "   - Protocol: VLESS"
echo "   - Port: 443"
echo "   - UUID: $UUID"
echo "   - Flow: xtls-rprx-vision"
echo "   - Security: Reality"
echo "   - Dest: www.apple.com:443"
echo "   - SNI: www.apple.com"
echo "   - Private Key: $PRIVATE_KEY"
