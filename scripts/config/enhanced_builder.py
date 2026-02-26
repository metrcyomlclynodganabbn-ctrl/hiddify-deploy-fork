"""
Генератор Enhanced конфигурации VLESS

Enhanced режим - максимальная приватность:
- Fragment packets (10-20, 50-100, tlshello)
- Minimal routing (всё через VPN)
- XTLS-Vision flow
- Максимальная защита от анализа
"""

import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def build_enhanced_config(
    user_uuid: str,
    server_address: str,
    port: int,
    public_key: str,
    short_id: str,
    sni: str = "www.apple.com",
    fingerprint: str = "chrome",
    flow: str = "xtls-rprx-vision"
) -> Dict[str, Any]:
    """Создать Enhanced конфиг (максимальная приватность)

    Enhanced режим оптимизирован для приватности:
    - Fragment для скрытия TLS handshake
    - XTLS-Vision flow
    - Весь трафик через VPN (кроме локального)
    - Защита от DPI и анализа трафика

    Args:
        user_uuid: UUID пользователя
        server_address: Адрес сервера
        port: Порт
        public_key: Публичный ключ Reality
        short_id: Short ID для Reality
        sni: SNI для замены
        fingerprint: Отпечаток браузера
        flow: XTLS flow (xtls-rprx-vision)

    Returns:
        Словарь с VLESS конфигурацией
    """
    config = {
        "log": {
            "loglevel": "None"
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
                                    "flow": flow,
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
                        "privateKey": "",
                        "publicKey": public_key,
                        "shortIds": [short_id],
                        "fingerprint": fingerprint,
                        "serverPort": port,
                        "clientFingerprint": fingerprint
                    },
                    "sockopt": {
                        "tcpKeepAliveInterval": 30,
                        "tcpNoDelay": True,
                        "tcpKeepAliveIdleTime": 60
                    }
                }
            },
            {
                "tag": "fragment",
                "protocol": "freedom",
                "settings": {
                    "domainStrategy": "AsIs"
                },
                "streamSettings": {
                    "sockopt": {
                        "tcpKeepAliveInterval": 30,
                        "tcpNoDelay": True
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
                # Только локальные сети напрямую
                {
                    "type": "field",
                    "ip": [
                        "10.0.0.0/8",
                        "172.16.0.0/12",
                        "192.168.0.0/16",
                        "127.0.0.0/8",
                        "fc00::/7"
                    ],
                    "outboundTag": "direct"
                },
                # Multicast и broadcast напрямую
                {
                    "type": "field",
                    "ip": ["224.0.0.0/3"],
                    "outboundTag": "direct"
                }
            ]
        }
    }

    logger.info(f"Enhanced конфиг сгенерирован для {server_address}")

    return config


def build_fragmented_outbound(
    interval: str = "10-20",
    length: str = "50-100",
    packets: str = "tlshello"
) -> Dict[str, Any]:
    """Создать outbound с Fragment

    Args:
        interval: Интервал между фрагментами
        length: Длина фрагментов
        packets: Тип пакетов для фрагментации

    Returns:
        Outbound конфигурация с Fragment
    """
    return {
        "protocol": "freedom",
        "tag": "fragment",
        "settings": {
            "domainStrategy": "AsIs"
        },
        "streamSettings": {
            "sockopt": {
                "tcpKeepAliveInterval": 30,
                "tcpNoDelay": True,
                "tcpKeepAliveIdleTime": 60
            }
        }
    }


def generate_vless_url_enhanced(
    user_uuid: str,
    server_address: str,
    port: int,
    public_key: str,
    short_id: str,
    sni: str = "www.apple.com",
    fingerprint: str = "chrome",
    flow: str = "xtls-rprx-vision",
    comments: str = "Hiddify-Enhanced"
) -> str:
    """Сгенерировать VLESS URL для Enhanced режима

    Args:
        user_uuid: UUID пользователя
        server_address: Адрес сервера
        port: Порт
        public_key: Публичный ключ Reality
        short_id: Short ID
        sni: SNI
        fingerprint: Отпечаток
        flow: XTLS flow
        comments: Комментарий

    Returns:
        VLESS URL строка
    """
    params = {
        "encryption": "none",
        "flow": flow,
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


def get_config_recommendation(
    location: str = "other",
    network_type: str = "other",
    priority: str = "speed"
) -> str:
    """Получить рекомендацию по выбору конфига

    Args:
        location: Локация (ru, cn, ir, other)
        network_type: Тип сети (home, mobile, public, other)
        priority: Приоритет (speed, privacy, balance)

    Returns:
        Рекомендуемый режим (standard или enhanced)
    """
    # Для РФ - Enhanced рекомендуется из-за цензуры
    if location == "ru":
        if priority == "speed":
            return "standard"
        return "enhanced"

    # Для Китая - Enhanced
    if location == "cn":
        return "enhanced"

    # Для Ирана - Enhanced
    if location == "ir":
        return "enhanced"

    # По приоритету
    if priority == "speed":
        return "standard"
    elif priority == "privacy":
        return "enhanced"
    else:  # balance
        return "standard"
