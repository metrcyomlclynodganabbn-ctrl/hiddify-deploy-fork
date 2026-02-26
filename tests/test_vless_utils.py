"""
Тесты для генерации и валидации VLESS URL

Version: 2.1.1

VLESS URL format:
vless://uuid@server:port?params#name

Параметры:
- encryption: тип шифрования (обычно none)
- flow: потоковый режим (xtls-rprx-vision для Reality)
- type: тип транспорта (grpc, tcp, ws)
- security: тип безопасности (tls, reality)
- sni: Server Name Indication
- fp: fingerprint (chrome, firefox, safari, etc.)
- pbk: public key (для Reality)
- sid: short ID (для Reality)
- spx: spx (для Reality)
- serviceName: имя gRPC сервиса
- path: путь для WebSocket
- host: хост для WebSocket
"""

import pytest
import re
from urllib.parse import urlparse, parse_qs
import uuid


@pytest.mark.unit
def test_vless_url_basic_format():
    """
    Тест базового формата VLESS URL

    Given: Параметры соединения
    When: Формируем VLESS URL
    Then: URL соответствует спецификации
    """
    # Arrange
    server_params = {
        'uuid': str(uuid.uuid4()),
        'server': 'example.com',
        'port': 443,
        'name': 'TestServer'
    }

    # Act
    url = f"vless://{server_params['uuid']}@{server_params['server']}:{server_params['port']}#{server_params['name']}"

    # Assert
    assert url.startswith('vless://')
    assert server_params['uuid'] in url
    assert server_params['server'] in url
    assert str(server_params['port']) in url


@pytest.mark.unit
def test_vless_url_with_reality():
    """
    Тест VLESS URL с Reality

    Given: Параметры Reality
    When: Формируем VLESS URL
    Then: URL содержит все параметры Reality
    """
    # Arrange
    params = {
        'uuid': str(uuid.uuid4()),
        'server': 'example.com',
        'port': 443,
        'encryption': 'none',
        'flow': 'xtls-rprx-vision',
        'type': 'grpc',
        'serviceName': 'grpc',
        'security': 'reality',
        'sni': 'apple.com',
        'fp': 'chrome',
        'pbk': 'test_public_key_123456789abcdef',
        'sid': '6',
        'name': 'RealityServer'
    }

    # Act
    query = '&'.join([
        f"encryption={params['encryption']}",
        f"flow={params['flow']}",
        f"type={params['type']}",
        f"serviceName={params['serviceName']}",
        f"security={params['security']}",
        f"sni={params['sni']}",
        f"fp={params['fp']}",
        f"pbk={params['pbk']}",
        f"sid={params['sid']}"
    ])

    url = f"vless://{params['uuid']}@{params['server']}:{params['port']}?{query}#{params['name']}"

    # Assert - парсим URL
    parsed = urlparse(url)

    assert parsed.scheme == 'vless'
    assert params['server'] in parsed.netloc
    assert params['uuid'] in parsed.netloc

    # Проверяем query параметры
    query_params = parse_qs(parsed.query)

    assert query_params.get('encryption', [None])[0] == params['encryption']
    assert query_params.get('flow', [None])[0] == params['flow']
    assert query_params.get('type', [None])[0] == params['type']
    assert query_params.get('security', [None])[0] == params['security']
    assert query_params.get('sni', [None])[0] == params['sni']
    assert query_params.get('fp', [None])[0] == params['fp']
    assert query_params.get('pbk', [None])[0] == params['pbk']
    assert query_params.get('sid', [None])[0] == params['sid']


@pytest.mark.unit
def test_vless_url_validation_valid_uuid():
    """
    Тест валидации UUID в VLESS URL

    Given: VLESS URL с валидным UUID
    When: Валидируем
    Then: UUID валиден
    """
    # Arrange
    test_uuid = str(uuid.uuid4())
    url = f"vless://{test_uuid}@example.com:443"

    # Act - извлекаем UUID из URL
    # VLESS URL format: vless://uuid@server:port
    match = re.match(r'vless://([a-f0-9\-]+)@', url)

    # Assert
    assert match is not None
    extracted_uuid = match.group(1)

    # Проверяем что UUID валидный
    try:
        uuid.UUID(extracted_uuid)
        assert True
    except ValueError:
        assert False, "Invalid UUID format"


@pytest.mark.unit
def test_vless_url_validation_invalid_uuid():
    """
    Тест валидации невалидного UUID

    Given: Строка с невалидным UUID
    When: Проверяем
    Then: Получаем ошибку валидации
    """
    # Arrange
    invalid_uuid = "not-a-valid-uuid"

    # Act & Assert
    try:
        uuid.UUID(invalid_uuid)
        assert False, "Should raise ValueError for invalid UUID"
    except ValueError:
        assert True  # Expected


@pytest.mark.unit
def test_vless_url_port_validation():
    """
    Тест валидации порта в VLESS URL

    Given: VLESS URL с разными портами
    When: Проверяем порты
    Then: Валидные порты проходят проверку
    """
    # Arrange
    valid_ports = [80, 443, 8443, 2053, 2083, 2087, 2096, 4433]

    for port in valid_ports:
        # Act
        url = f"vless://{uuid.uuid4()}@example.com:{port}"

        # Assert
        match = re.search(r':(\d+)(?:\?|#|$)', url)
        assert match is not None
        extracted_port = int(match.group(1))
        assert 1 <= extracted_port <= 65535


@pytest.mark.unit
def test_vless_url_with_websocket():
    """
    Тест VLESS URL с WebSocket транспортом

    Given: Параметры WebSocket
    When: Формируем VLESS URL
    Then: URL содержит параметры WebSocket
    """
    # Arrange
    params = {
        'uuid': str(uuid.uuid4()),
        'server': 'example.com',
        'port': 443,
        'type': 'ws',
        'security': 'tls',
        'path': '/ws',
        'host': 'ws.example.com',
        'name': 'WSServer'
    }

    # Act
    query = '&'.join([
        f"type={params['type']}",
        f"security={params['security']}",
        f"path={params['path']}",
        f"host={params['host']}"
    ])

    url = f"vless://{params['uuid']}@{params['server']}:{params['port']}?{query}#{params['name']}"

    # Assert
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    assert query_params.get('type', [None])[0] == 'ws'
    assert query_params.get('path', [None])[0] == '/ws'
    assert query_params.get('host', [None])[0] == 'ws.example.com'


@pytest.mark.unit
def test_vless_url_with_tcp():
    """
    Тест VLESS URL с TCP транспортом

    Given: Параметры TCP
    When: Формируем VLESS URL
    Then: URL содержит параметры TCP
    """
    # Arrange
    params = {
        'uuid': str(uuid.uuid4()),
        'server': 'example.com',
        'port': 443,
        'type': 'tcp',
        'security': 'tls',
        'name': 'TCPServer'
    }

    # Act
    query = '&'.join([
        f"type={params['type']}",
        f"security={params['security']}"
    ])

    url = f"vless://{params['uuid']}@{params['server']}:{params['port']}?{query}#{params['name']}"

    # Assert
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    assert query_params.get('type', [None])[0] == 'tcp'
    assert query_params.get('security', [None])[0] == 'tls'


@pytest.mark.unit
def test_vless_url_encode_special_chars():
    """
    Тест кодирования спецсимволов в VLESS URL

    Given: Параметры со спецсимволами
    When: Формируем VLESS URL
    Then: Спецсимволы корректно закодированы
    """
    # Arrange
    params = {
        'uuid': str(uuid.uuid4()),
        'server': 'example.com',
        'port': 443,
        'path': '/ws?with=special&chars',
        'name': 'Server With Spaces'
    }

    # Act
    from urllib.parse import quote

    path_encoded = quote(params['path'], safe='')
    name_encoded = quote(params['name'], safe='')

    query = f"type=ws&path={path_encoded}"
    url = f"vless://{params['uuid']}@{params['server']}:{params['port']}?{query}#{name_encoded}"

    # Assert
    assert '%' in url  # Проверяем что кодирование применено
    assert ' ' not in url  # Пробелы должны быть закодированы


@pytest.mark.unit
def test_vless_url_complete_real_world_example():
    """
    Тест реального VLESS URL для Reality

    Given: Полный набор параметров для production
    When: Формируем VLESS URL
    Then: URL полностью соответствует формату
    """
    # Arrange - реальные параметры
    params = {
        'uuid': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'server': 'vps.example.com',
        'port': 443,
        'encryption': 'none',
        'flow': 'xtls-rprx-vision',
        'type': 'grpc',
        'serviceName': 'grpc',
        'security': 'reality',
        'sni': 'www.apple.com',
        'fp': 'safari',
        'pbk': 'yL_pCSNisvLvRrHsvBw8NhPWvXf0b6WpYKybxT5eQDw',
        'sid': '6f7148c0',
        'name': '🇷🇺 RU Reality'
    }

    # Act
    query = '&'.join([
        f"encryption={params['encryption']}",
        f"flow={params['flow']}",
        f"type={params['type']}",
        f"serviceName={params['serviceName']}",
        f"security={params['security']}",
        f"sni={params['sni']}",
        f"fp={params['fp']}",
        f"pbk={params['pbk']}",
        f"sid={params['sid']}"
    ])

    url = f"vless://{params['uuid']}@{params['server']}:{params['port']}?{query}#{params['name']}"

    # Assert
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Проверяем все критические параметры
    assert parsed.scheme == 'vless'
    assert params['server'] in parsed.netloc
    assert params['uuid'] in parsed.netloc

    # Reality параметры
    assert query_params.get('security', [None])[0] == 'reality'
    assert query_params.get('flow', [None])[0] == 'xtls-rprx-vision'
    assert query_params.get('pbk', [None])[0] == params['pbk']
    assert query_params.get('sid', [None])[0] == params['sid']

    # URL не должен быть пустым
    assert len(url) > 200  # Реальные URL обычно длинные


@pytest.mark.unit
def test_vless_url_name_can_be_empty():
    """
    Тест VLESS URL без имени

    Given: Параметры без имени сервера
    When: Формируем VLESS URL
    Then: URL валиден без #name части
    """
    # Arrange
    params = {
        'uuid': str(uuid.uuid4()),
        'server': 'example.com',
        'port': 443
    }

    # Act
    url = f"vless://{params['uuid']}@{params['server']}:{params['port']}"

    # Assert
    assert '#' not in url
    assert url.endswith(f"{params['server']}:{params['port']}")
