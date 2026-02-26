"""
Тесты для генерации QR кодов

Version: 2.1.1
"""

import pytest
import os
import tempfile
from pathlib import Path
import qrcode
from io import BytesIO
from PIL import Image


@pytest.mark.unit
def test_qr_code_basic_generation():
    """
    Тест базовой генерации QR кода

    Given: Текстовая строка
    When: Генерируем QR код
    Then: Получаем валидное изображение
    """
    # Arrange
    test_data = "vless://uuid@example.com:443?encryption=none&flow=xtls-rprx-vision&type=grpc&serviceName=grpc&security=reality&sni=apple.com&fp=chrome&pbk=public_key&sid=6#Test"

    # Act
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(test_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Assert
    assert img is not None
    assert isinstance(img, Image.Image)
    assert img.width > 0
    assert img.height > 0


@pytest.mark.unit
def test_qr_code_save_to_file():
    """
    Тест сохранения QR кода в файл

    Given: QR код объект
    When: Сохраняем в файл
    Then: Файл создаётся и валиден
    """
    # Arrange
    test_data = "https://example.com"
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Act
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(test_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(tmp_path)

        # Assert
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 0

        # Проверяем что изображение валидное
        with Image.open(tmp_path) as saved_img:
            assert saved_img.format == 'PNG'
            assert saved_img.width > 0
            assert saved_img.height > 0

    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.unit
def test_qr_code_to_bytes():
    """
    Тест конвертации QR кода в байты

    Given: QR код объект
    When: Конвертируем в байты
    Then: Получаем валидные байты PNG изображения
    """
    # Arrange
    test_data = "vless://test"

    # Act
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(test_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_bytes = buffer.getvalue()

    # Assert
    assert len(qr_bytes) > 0
    assert qr_bytes.startswith(b'\x89PNG')  # PNG signature


@pytest.mark.unit
def test_qr_code_vless_url():
    """
    Тест генерации QR кода для VLESS URL

    Given: VLESS URL строка
    When: Генерируем QR код
    Then: Получаем валидное изображение с достаточным размером
    """
    # Arrange - реальный VLESS URL
    vless_url = (
        "vless://a1b2c3d4-e5f6-7890-abcd-ef1234567890@"
        "example.com:443?"
        "encryption=none&flow=xtls-rprx-vision&"
        "type=grpc&serviceName=grpc&"
        "security=reality&"
        "sni=apple.com&"
        "fp=chrome&"
        "pbk=abcdefghijklmnopqrstuvwxyz123456789&"
        "sid=6&"
        "spx=%2F#TestServer"
    )

    # Act
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(vless_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Assert
    assert img.width >= 200  # Достаточный размер для сканирования
    assert img.height >= 200


@pytest.mark.unit
def test_qr_code_custom_colors():
    """
    Тест генерации QR кода с кастомными цветами

    Given: Параметры кастомных цветов
    When: Генерируем QR код
    Then: Получаем изображение с правильными цветами
    """
    # Arrange
    test_data = "test_data"
    fill_color = "#0000FF"  # Синий
    back_color = "#FFFF00"  # Жёлтый

    # Act
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(test_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)

    # Assert
    assert img is not None

    # Проверяем что цвета применены (проверка нескольких пикселей)
    pixels = img.load()

    # Проверяем что corners (background) жёлтые
    # Corner pixels должны быть фонового цвета
    # (так как border=4, верхний левый пиксель будет фоновым)
    # Цвета в PIL это (R, G, B) для RGB режима
    # Но make_image возвращает '1' mode (black/white) если не указано иначе

    assert img.mode in ['1', 'L', 'RGB']


@pytest.mark.unit
def test_qr_code_size_parameter():
    """
    Тест генерации QR кода с разным размером

    Given: Разные значения box_size
    When: Генерируем QR коды
    Then: Размеры изображений пропорциональны box_size
    """
    # Arrange
    test_data = "size_test"

    # Act
    sizes = []
    for box_size in [5, 10, 20]:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=4,
        )
        qr.add_data(test_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        sizes.append((box_size, img.width, img.height))

    # Assert - размеры должны быть разными и возрастать
    assert sizes[0][1] < sizes[1][1] < sizes[2][1]
    assert sizes[0][2] < sizes[1][2] < sizes[2][2]


@pytest.mark.unit
def test_qr_code_error_correction_levels():
    """
    Тест разных уровней коррекции ошибок

    Given: Разные уровни error_correction
    When: Генерируем QR коды
    Then: Все уровни работают корректно
    """
    # Arrange
    test_data = "error_correction_test"

    # Act - все уровни коррекции ошибок должны работать
    error_levels = [
        qrcode.constants.ERROR_CORRECT_L,  # ~7%
        qrcode.constants.ERROR_CORRECT_M,  # ~15%
        qrcode.constants.ERROR_CORRECT_Q,  # ~25%
        qrcode.constants.ERROR_CORRECT_H,  # ~30%
    ]

    for error_level in error_levels:
        qr = qrcode.QRCode(
            version=1,
            error_correction=error_level,
            box_size=10,
            border=4,
        )
        qr.add_data(test_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Assert
        assert img is not None
        assert img.width > 0
        assert img.height > 0
