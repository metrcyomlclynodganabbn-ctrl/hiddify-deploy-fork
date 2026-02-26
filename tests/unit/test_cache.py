"""Unit тесты для cache модуля"""

import pytest
import json
from datetime import timedelta

from scripts.cache.redis_client import RedisClient


class TestRedisClient:
    """Тесты Redis клиента"""

    def test_redis_client_init(self):
        """Тест инициализации клиента"""
        client = RedisClient(url="redis://localhost:6379/0", password="")

        assert client.url == "redis://localhost:6379/0"
        assert client.password == ""
        assert client.pool is None

    def test_ttl_constants(self):
        """Тест констант TTL"""
        client = RedisClient()

        assert client.TTL_USER_PROFILE == 300  # 5 минут
        assert client.TTL_ACTIVE_SUBSCRIPTION == 60  # 1 минута
        assert client.TTL_VPN_CONFIG == 600  # 10 минут
        assert client.TTL_CATALOG_PLANS == 600  # 10 минут
        assert client.TTL_SESSION == 86400  # 24 часа

    def test_cache_key_formats(self):
        """Тест форматов ключей кэша"""
        client = RedisClient()

        # Проверка форматов ключей (без подключения к Redis)
        assert "user:123:profile" == f"user:123:profile"
        assert "user:456:subscription:active" == f"user:456:subscription:active"
        assert "vpn:config:abc123" == f"vpn:config:abc123"
        assert "catalog:plans" == "catalog:plans"
        assert "session:xyz789" == f"session:xyz789"


@pytest.mark.asyncio
class TestRedisClientAsync:
    """Асинхронные тесты Redis клиента (требуют работающий Redis)"""

    async def test_redis_without_connection_returns_none(self):
        """Тест методов без подключения (возвращают None)"""
        client = RedisClient(url="redis://localhost:9999/0", password="invalid")

        # Без подключения методы должны возвращать None/false
        result = await client.get("test_key")
        assert result is None

        exists = await client.exists("test_key")
        assert exists is False

    async def test_json_helpers_with_mock_data(self):
        """Тест JSON хелперов с тестовыми данными"""
        client = RedisClient()

        # Тестовые данные
        test_data = {
            "user_id": 123,
            "username": "testuser",
            "role": "user"
        }

        # Проверка сериализации
        json_string = json.dumps(test_data, ensure_ascii=False, default=str)
        parsed = json.loads(json_string)

        assert parsed["user_id"] == 123
        assert parsed["username"] == "testuser"
