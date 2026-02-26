#!/usr/bin/env python3
"""
VLESS URL Generator for Telegram Bot
Добавить этот код в monitor_bot.py
"""

def generate_vless_url(user_uuid: str, server_ip: str, port: int,
                        public_key: str, sni: str = "www.apple.com",
                        flow: str = "xtls-rprx-vision") -> str:
    """
    Генерирует VLESS-Reality URL для импорта в клиент

    Args:
        user_uuid: UUID пользователя
        server_ip: IP адрес сервера
        port: Порт (обычно 443)
        public_key: Публичный ключ Reality
        sni: SNI (Server Name Indication)
        flow: Flow (обычно xtls-rprx-vision)

    Returns:
        VLESS URL для импорта
    """
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

    url = f"{base}?{'&'.join(params)}#SKRT-VPN"
    return url


def generate_qr_code(url: str):
    """
    Генерирует QR код для VLESS URL

    Args:
        url: VLESS URL

    Returns:
        Photo object для отправки в Telegram
    """
    import qrcode
    from io import BytesIO
    import tempfile

    # Создаём QR код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Создаём изображение
    img = qr.make_image(fill_color="black", back_color="white")

    # Сохраняем во временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(temp_file, format='PNG')
    temp_file.close()

    return temp_file.name


# Пример использования:
if __name__ == "__main__":
    # Тестовые данные
    uuid = "1752a3e1-314f-4864-8fbb-234e86c11558"
    server = "5.45.114.73"
    port = 443
    public_key = "whqp8uteAFCE34Pdnq__-M0RlSKJYnAxcxTl7DQzhI0"

    url = generate_vless_url(uuid, server, port, public_key)
    print("VLESS URL:")
    print(url)

    # Генерация QR кода
    qr_file = generate_qr_code(url)
    print(f"\nQR код сохранён: {qr_file}")
