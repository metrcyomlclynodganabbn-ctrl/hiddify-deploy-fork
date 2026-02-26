#!/usr/bin/env python3
"""
VLESS URL Generator Utility v2.1
Генерация VLESS-Reality URL с параметрами
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

VPS_IP = os.getenv('VPS_IP', '5.45.114.73')
VLESS_PORT = int(os.getenv('VLESS_PORT', '443'))
REALITY_PUBLIC_KEY = os.getenv('REALITY_PUBLIC_KEY', '')
REALITY_SNI = os.getenv('REALITY_SNI', 'www.apple.com')
REALITY_FINGERPRINT = os.getenv('REALITY_FINGERPRINT', 'chrome')


def generate_vless_url(
    user_uuid: str,
    ip: str = VPS_IP,
    port: int = VLESS_PORT,
    public_key: str = REALITY_PUBLIC_KEY,
    sni: str = REALITY_SNI,
    fingerprint: str = REALITY_FINGERPRINT,
    short_id: str = "",
    flow: str = "xtls-rprx-vision",
    name: str = "SKRT-VPN"
) -> str:
    """
    Генерация VLESS-Reality URL

    Параметры:
        user_uuid: UUID пользователя
        ip: IP адрес сервера (по умолчанию из .env)
        port: Порт (по умолчанию 443)
        public_key: Публичный ключ Reality (из .env)
        sni: SNI для маскировки (по умолчанию www.apple.com)
        fingerprint: TLS fingerprint (по умолчанию chrome)
        short_id: Short ID для Reality (пустая строка = случайный)
        flow: Flow режим (xtls-rprx-vision)
        name: Имя конфига

    Возвращает:
        VLESS URL в формате: vless://uuid@ip:port?params#name
    """

    base = f"vless://{user_uuid}@{ip}:{port}"

    params = (
        f"?encryption=none"
        f"&flow={flow}"
        f"&security=reality"
        f"&sni={sni}"
        f"&fp={fingerprint}"
        f"&pbk={public_key}"
        f"&sid={short_id}"
        f"&type=tcp"
        f"&header=none"
    )

    return f"{base}{params}#{name}"


def parse_vless_url(url: str) -> dict:
    """
    Парсинг VLESS URL

    Параметры:
        url: VLESS URL

    Возвращает:
        Словарь с параметрами
    """

    from urllib.parse import urlparse, parse_qs, unquote

    parsed = urlparse(url)

    if parsed.scheme != 'vless':
        raise ValueError("Not a VLESS URL")

    # UUID@host:port
    auth = parsed.netloc
    user_uuid, _, host_port = auth.partition('@')
    host, _, port = host_port.partition(':')

    # Query параметры
    params = parse_qs(parsed.query)

    return {
        'uuid': user_uuid,
        'host': host,
        'port': int(port) if port else 443,
        'encryption': params.get('encryption', ['none'])[0],
        'flow': params.get('flow', [''])[0],
        'security': params.get('security', ['reality'])[0],
        'sni': params.get('sni', [''])[0],
        'fingerprint': params.get('fp', ['chrome'])[0],
        'public_key': params.get('pbk', [''])[0],
        'short_id': params.get('sid', [''])[0],
        'type': params.get('type', ['tcp'])[0],
        'name': unquote(parsed.fragment) if parsed.fragment else 'VLESS'
    }


def validate_vless_url(url: str) -> bool:
    """
    Валидация VLESS URL

    Параметры:
        url: VLESS URL

    Возвращает:
        True если валидный, False если нет
    """

    try:
        parsed = parse_vless_url(url)

        # Обязательные поля
        required = ['uuid', 'host', 'port', 'public_key']

        for field in required:
            if not parsed.get(field):
                return False

        # UUID валидация
        import uuid
        try:
            uuid.UUID(parsed['uuid'])
        except ValueError:
            return False

        # Порт валидация
        if not (1 <= parsed['port'] <= 65535):
            return False

        return True

    except Exception:
        return False


if __name__ == '__main__':
    # Тест генерации
    test_uuid = "acb6768e-8f1c-48bc-ac24-2898b65a8946"

    url = generate_vless_url(
        user_uuid=test_uuid,
        name="SKRT-VPN-Test"
    )

    print(f"Сгенерированный VLESS URL:")
    print(url)
    print()

    # Валидация
    is_valid = validate_vless_url(url)
    print(f"Валидация: {'✅ OK' if is_valid else '❌ Ошибка'}")
    print()

    # Парсинг
    parsed = parse_vless_url(url)
    print(f"Распарсенные параметры:")
    for key, value in parsed.items():
        print(f"  {key}: {value}")
