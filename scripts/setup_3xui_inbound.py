#!/usr/bin/env python3
"""
Setup VLESS-Reality inbound in 3X-ui panel
"""
import requests
import json
import uuid

# 3X-ui panel credentials
PANEL_URL = "https://5.45.114.73:2053/XMWc515djPCq2ohc11"
USERNAME = "admin"
PASSWORD = "T7QC9oj8gx4FxyB9"

def login():
    """Login to 3X-ui panel"""
    session = requests.Session()
    session.verify = False  # Ignore SSL

    # Login
    response = session.post(
        f"{PANEL_URL}/login",
        json={
            "username": USERNAME,
            "password": PASSWORD
        }
    )

    if response.status_code == 200:
        print("✅ Logged in to 3X-ui panel")
        return session
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None

def create_vless_reality_inbound(session):
    """Create VLESS-Reality inbound"""

    # Generate keys
    import subprocess
    result = subprocess.run(
        ["/usr/local/x-ui/bin/xray", "x25519"],
        capture_output=True,
        text=True
    )

    private_key = None
    public_key = None

    for line in result.stdout.split('\n'):
        if 'Private key' in line:
            private_key = line.split(': ')[1].strip()
        if 'Public key' in line:
            public_key = line.split(': ')[1].strip()

    if not private_key or not public_key:
        print("❌ Failed to generate keys")
        return None

    print(f"✅ Keys generated:")
    print(f"   Private: {private_key}")
    print(f"   Public: {public_key}")

    # Create inbound config
    inbound_config = {
        "remark": "VLESS-Reality",
        "port": 443,
        "protocol": "vless",
        "settings": {
            "clients": [
                {
                    "id": str(uuid.uuid4()),
                    "flow": "xtls-rprx-vision",
                    "email": "admin@skrt.vpn"
                }
            ],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "dest": "www.apple.com:443",
                "serverNames": ["www.apple.com", "apple.com"],
                "privateKey": private_key,
                "shortIds": [""]
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    }

    # Create inbound via API
    response = session.post(
        f"{PANEL_URL}/panel/inbound/add",
        json=inbound_config
    )

    if response.status_code == 200:
        print("✅ VLESS-Reality inbound created")
        result = response.json()
        return result
    else:
        print(f"❌ Failed to create inbound: {response.status_code}")
        print(response.text)
        return None

def main():
    print("🚀 Setting up VLESS-Reality inbound in 3X-ui")

    session = login()
    if not session:
        return

    inbound = create_vless_reality_inbound(session)
    if inbound:
        print("✅ Inbound configured successfully")
        print("\n📋 Client configuration:")
        print(f"   UUID: {inbound.get('client_id', 'N/A')}")
        print(f"   Public Key: {inbound.get('public_key', 'N/A')}")
        print(f"   Port: 443")
        print(f"   Server: 5.45.114.73")

if __name__ == "__main__":
    main()
