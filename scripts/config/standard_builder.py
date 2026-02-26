"""
Генератор Standard конфигурации VLESS

Standard режим - быстрый конфиг с smart routing:
- Минимальные накладные расходы
- Торренты без прокси
- Smart routing для популярных сервисов
- Максимальная скорость
"""

import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def build_standard_config(
    user_uuid: str,
    server_address: str,
    port: int,
    public_key: str,
    short_id: str,
    sni: str = "www.apple.com",
    fingerprint: str = "chrome"
) -> Dict[str, Any]:
    """Создать Standard конфиг (быстрый, с smart routing)

    Standard режим оптимизирован для скорости:
    - Отсутствует Fragment (меньше задержек)
    - Smart routing directs LAN и китайские ресурсы напрямую
    - Торренты идут напрямую
    - Минимальные накладные расходы

    Args:
        user_uuid: UUID пользователя
        server_address: Адрес сервера
        port: Порт
        public_key: Публичный ключ Reality
        short_id: Short ID для Reality
        sni: SNI для замены
        fingerprint: Отпечаток браузера

    Returns:
        Словарь с VLESS конфигурацией
    """
    config = {
        "log": {
            "loglevel": "None"  # Отключаем логи для производительности
        },
        "inbounds": [
            {
                "port": 10808,
                "protocol": "socks",
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic", "fakedns"],
                    "routeOnly": False
                },
                "settings": {
                    "auth": "noauth",
                    "udp": True
                }
            },
            {
                "port": 10809,
                "protocol": "http",
                "settings": {
                    "timeout": 0
                }
            }
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": server_address,
                            "port": port,
                            "users": [
                                {
                                    "id": user_uuid,
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
                        "dest": f"{sni}:443",
                        "serverNames": [sni],
                        "privateKey": "",  # Заполняется на сервере
                        "publicKey": public_key,
                        "shortIds": [short_id],
                        "fingerprint": fingerprint,
                        "serverPort": port,
                        "clientFingerprint": fingerprint
                    }
                }
            },
            {
                "tag": "direct",
                "protocol": "freedom",
                "settings": {
                    "domainStrategy": "AsIs"
                }
            },
            {
                "tag": "block",
                "protocol": "blackhole",
                "settings": {}
            }
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                # Локальные сети напрямую
                {
                    "type": "field",
                    "ip": [
                        "10.0.0.0/8",
                        "172.16.0.0/12",
                        "192.168.0.0/16",
                        "127.0.0.0/8"
                    ],
                    "outboundTag": "direct"
                },
                # Китай напрямую (для скорости)
                {
                    "type": "field",
                    "domain": [
                        "geosite:cn"
                    ],
                    "outboundTag": "direct"
                },
                # Торренты напрямую (используют специфические порты)
                {
                    "type": "field",
                    "port": "6881-6889,51413,51415",
                    "outboundTag": "direct"
                },
                # Private DNS
                {
                    "type": "field",
                    "ip": ["224.0.0.0/3", "fc00::/7"],
                    "outboundTag": "direct"
                },
                # STUN
                {
                    "type": "field",
                    "port": "3478,5349",
                    "outboundTag": "direct"
                }
            ]
        }
    }

    logger.info(f"Standard конфиг сгенерирован для {server_address}")

    return config


def generate_vless_url(
    user_uuid: str,
    server_address: str,
    port: int,
    public_key: str,
    short_id: str,
    sni: str = "www.apple.com",
    fingerprint: str = "chrome",
    comments: str = "Hiddify-Standard"
) -> str:
    """Сгенерировать VLESS URL для Standard режима

    Args:
        user_uuid: UUID пользователя
        server_address: Адрес сервера
        port: Порт
        public_key: Публичный ключ Reality
        short_id: Short ID
        sni: SNI
        fingerprint: Отпечаток
        comments: Комментарий

    Returns:
        VLESS URL строка
    """
    params = {
        "encryption": "none",
        "security": "reality",
        "sni": sni,
        "fp": fingerprint,
        "pbk": public_key,
        "sid": short_id,
        "type": "tcp",
        "comment": comments
    }

    # Формирование query string
    query = "&".join(f"{k}={v}" for k, v in params.items())
    vless_url = f"vless://{user_uuid}@{server_address}:{port}?{query}#{comments}"

    return vless_url
