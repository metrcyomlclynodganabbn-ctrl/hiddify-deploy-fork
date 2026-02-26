#!/usr/bin/env python3
"""
QR Code Generator Module v2.1
Генерация QR кодов для VPN конфигов
"""

import qrcode
from io import BytesIO
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


def generate_qr_code(
    url: str,
    size: int = 10,
    border: int = 5,
    box_size: int = 10,
    version: int = 1
) -> BytesIO:
    """
    Генерация QR кода

    Параметры:
        url: URL для кодирования (VLESS/SS/Hysteria2)
        size: Размер QR кода (рекомендуется 10-15)
        border: Отступ (рекомендуется 4-5)
        box_size: Размер одного квадрата (пиксели)
        version: Версия QR (1-40, 1 = auto)

    Возвращает:
        BytesIO с PNG изображением
    """

    qr = qrcode.QRCode(
        version=version,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )

    qr.add_data(url)
    qr.make(fit=True)

    # Создание изображения
    img = qr.make_image(fill_color="black", back_color="white")

    # Конвертация в BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer


def generate_qr_with_logo(
    url: str,
    logo_path: Optional[str] = None,
    box_size: int = 10,
    border: int = 5
) -> BytesIO:
    """
    Генерация QR кода с логотипом в центре

    Параметры:
        url: URL для кодирования
        logo_path: Путь к файлу логотипа (опционально)
        box_size: Размер одного квадрата
        border: Отступ

    Возвращает:
        BytesIO с PNG изображением
    """

    # Создаем базовый QR код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High для логотипа
        box_size=box_size,
        border=border,
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Добавляем логотип если указан
    if logo_path:
        try:
            logo = Image.open(logo_path)

            # Размер логотипа ~20% от QR кода
            qr_width, qr_height = img.size
            logo_size = min(qr_width, qr_height) // 5

            # Ресайз логотипа
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            # Позиция логотипа (центр)
            pos = (
                (qr_width - logo_size) // 2,
                (qr_height - logo_size) // 2
            )

            # Вставляем логотип
            img.paste(logo, pos, logo if logo.mode == 'RGBA' else None)

        except Exception as e:
            print(f"⚠️  Не удалось добавить логотип: {e}")

    # Конвертация в BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer


def generate_styled_qr(
    url: str,
    foreground_color: str = "000000",
    background_color: str = "FFFFFF",
    box_size: int = 10,
    border: int = 5
) -> BytesIO:
    """
    Генерация стилизованного QR кода с кастомными цветами

    Параметры:
        url: URL для кодирования
        foreground_color: HEX цвет переднего плана (с решеткой)
        background_color: HEX цвет фона (с решеткой)
        box_size: Размер одного квадрата
        border: Отступ

    Возвращает:
        BytesIO с PNG изображением
    """

    # Конвертация HEX в RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color=hex_to_rgb(foreground_color),
        back_color=hex_to_rgb(background_color)
    )

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer


def save_qr_to_file(buffer: BytesIO, file_path: str) -> None:
    """
    Сохранить QR код в файл

    Параметры:
        buffer: BytesIO с изображением
        file_path: Путь для сохранения
    """

    with open(file_path, 'wb') as f:
        f.write(buffer.getvalue())


if __name__ == '__main__':
    # Тест генерации
    test_url = "vless://acb6768e-8f1c-48bc-ac24-2898b65a8946@5.45.114.73:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.apple.com&fp=chrome&pbk=6b8DFSyCtfdBUNLkgU2QtgQTLUu_3F9RQhvcf2CuHn0&type=tcp&header=none#SKRT-VPN"

    print("Генерация QR кода...")
    buffer = generate_qr_code(test_url)

    # Сохранение для теста
    output_path = "/tmp/test_qr.png"
    save_qr_to_file(buffer, output_path)

    print(f"✅ QR код сохранен: {output_path}")
    print(f"   Размер: {len(buffer.getvalue())} bytes")
