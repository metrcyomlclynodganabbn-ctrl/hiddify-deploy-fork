"""
Redis клиент для кэширования данных

Модуль предоставляет асинхронный Redis клиент для кэширования:
- Профилей пользователей
- Подписок
- VPN конфигураций
- Каталога планов

Использует redis.asyncio для асинхронных операций.
"""

import os
import json
import logging
from typing import Optional, Any, Dict
from datetime import timedelta

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Асинхронный Redis клиент с поддержкой сериализации JSON

    Attributes:
        url: URL подключения к Redis
        password: Пароль для аутентификации
        pool: Пул соединений Redis
    """

    # TTL константы (в секундах)
    TTL_USER_PROFILE = 300  # 5 минут
    TTL_ACTIVE_SUBSCRIPTION = 60  # 1 минута
    TTL_VPN_CONFIG = 600  # 10 минут
    TTL_CATALOG_PLANS = 600  # 10 минут
    TTL_SESSION = 86400  # 24 часа

    def __init__(self, url: str = None, password: str = None):
        """Инициализация Redis клиента

        Args:
            url: URL подключения (redis://localhost:6379/0)
            password: Пароль для аутентификации
        """
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.password = password or os.getenv("REDIS_PASSWORD", "")
        self.pool: Optional[aioredis.Redis] = None

    async def connect(self) -> bool:
        """Установить соединение с Redis

        Returns:
            True если соединение установлено, False иначе
        """
        if not aioredis:
            logger.warning("redis.asyncio не установлен, кэширование отключено")
            return False

        try:
            self.pool = aioredis.from_url(
                self.url,
                password=self.password if self.password else None,
                encoding="utf-8",
                decode_responses=True
            )
            # Проверка соединения
            await self.pool.ping()
            logger.info(f"Redis подключен: {self.url}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к Redis: {e}")
            self.pool = None
            return False

    async def close(self):
        """Закрыть соединение с Redis"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Redis соединение закрыто")

    async def get(self, key: str) -> Optional[str]:
        """Получить значение из кэша

        Args:
            key: Ключ кэша

        Returns:
            Значение из кэша или None
        """
        if not self.pool:
            return None
        try:
            return await self.pool.get(key)
        except Exception as e:
            logger.error(f"Ошибка чтения из Redis (key={key}): {e}")
            return None

    async def setex(self, key: str, seconds: int, value: str):
        """Сохранить значение в кэше с TTL

        Args:
            key: Ключ кэша
            seconds: TTL в секундах
            value: Значение для сохранения
        """
        if not self.pool:
            return
        try:
            await self.pool.setex(key, seconds, value)
        except Exception as e:
            logger.error(f"Ошибка записи в Redis (key={key}): {e}")

    async def delete(self, key: str):
        """Удалить ключ из кэша

        Args:
            key: Ключ для удаления
        """
        if not self.pool:
            return
        try:
            await self.pool.delete(key)
        except Exception as e:
            logger.error(f"Ошибка удаления из Redis (key={key}): {e}")

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа

        Args:
            key: Ключ для проверки

        Returns:
            True если ключ существует
        """
        if not self.pool:
            return False
        try:
            return await self.pool.exists(key) > 0
        except Exception as e:
            logger.error(f"Ошибка проверки ключа в Redis (key={key}): {e}")
            return False

    # === JSON хелперы ===

    async def get_json(self, key: str) -> Optional[Any]:
        """Получить JSON значение из кэша

        Args:
            key: Ключ кэша

        Returns:
            Десериализованный JSON объект или None
        """
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка десериализации JSON (key={key}): {e}")
        return None

    async def set_json(self, key: str, seconds: int, value: Any):
        """Сохранить JSON значение в кэш

        Args:
            key: Ключ кэша
            seconds: TTL в секундах
            value: Объект для сериализации
        """
        try:
            json_value = json.dumps(value, ensure_ascii=False, default=str)
            await self.setex(key, seconds, json_value)
        except Exception as e:
            logger.error(f"Ошибка сериализации JSON (key={key}): {e}")

    # === Кэш профилей ===

    async def get_user_profile(self, telegram_id: int) -> Optional[Dict]:
        """Получить профиль пользователя из кэша

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            Словарь с профилем или None
        """
        cache_key = f"user:{telegram_id}:profile"
        return await self.get_json(cache_key)

    async def set_user_profile(self, telegram_id: int, profile: Dict):
        """Сохранить профиль пользователя в кэш

        Args:
            telegram_id: Telegram ID пользователя
            profile: Словарь с профилем
        """
        cache_key = f"user:{telegram_id}:profile"
        await self.set_json(cache_key, self.TTL_USER_PROFILE, profile)

    async def invalidate_user_profile(self, telegram_id: int):
        """Инвалидировать кэш профиля пользователя

        Args:
            telegram_id: Telegram ID пользователя
        """
        cache_key = f"user:{telegram_id}:profile"
        await self.delete(cache_key)

    # === Кэш подписок ===

    async def get_active_subscription(self, user_id: int) -> Optional[Dict]:
        """Получить активную подписку из кэша

        Args:
            user_id: ID пользователя

        Returns:
            Словарь с подпиской или None
        """
        cache_key = f"user:{user_id}:subscription:active"
        return await self.get_json(cache_key)

    async def set_active_subscription(self, user_id: int, subscription: Dict):
        """Сохранить активную подписку в кэш

        Args:
            user_id: ID пользователя
            subscription: Словарь с подпиской
        """
        cache_key = f"user:{user_id}:subscription:active"
        await self.set_json(cache_key, self.TTL_ACTIVE_SUBSCRIPTION, subscription)

    async def invalidate_active_subscription(self, user_id: int):
        """Инвалидировать кэш активной подписки

        Args:
            user_id: ID пользователя
        """
        cache_key = f"user:{user_id}:subscription:active"
        await self.delete(cache_key)

    # === Кэш VPN конфигураций ===

    async def get_vpn_config(self, vpn_account_id: str) -> Optional[Dict]:
        """Получить VPN конфигурацию из кэша

        Args:
            vpn_account_id: ID VPN аккаунта

        Returns:
            Словарь с конфигурацией или None
        """
        cache_key = f"vpn:config:{vpn_account_id}"
        return await self.get_json(cache_key)

    async def set_vpn_config(self, vpn_account_id: str, config: Dict):
        """Сохранить VPN конфигурацию в кэш

        Args:
            vpn_account_id: ID VPN аккаунта
            config: Словарь с конфигурацией
        """
        cache_key = f"vpn:config:{vpn_account_id}"
        await self.set_json(cache_key, self.TTL_VPN_CONFIG, config)

    # === Кэш каталога планов ===

    async def get_catalog_plans(self) -> Optional[list]:
        """Получить каталог планов из кэша

        Returns:
            Список планов или None
        """
        cache_key = "catalog:plans"
        return await self.get_json(cache_key)

    async def set_catalog_plans(self, plans: list):
        """Сохранить каталог планов в кэш

        Args:
            plans: Список планов
        """
        cache_key = "catalog:plans"
        await self.set_json(cache_key, self.TTL_CATALOG_PLANS, plans)

    async def invalidate_catalog_plans(self):
        """Инвалидировать кэш каталога планов"""
        cache_key = "catalog:plans"
        await self.delete(cache_key)

    # === Кэш сессий ===

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Получить данные сессии из кэша

        Args:
            session_id: ID сессии

        Returns:
            Словарь с данными сессии или None
        """
        cache_key = f"session:{session_id}"
        return await self.get_json(cache_key)

    async def set_session(self, session_id: str, data: Dict):
        """Сохранить данные сессии в кэш

        Args:
            session_id: ID сессии
            data: Данные сессии
        """
        cache_key = f"session:{session_id}"
        await self.set_json(cache_key, self.TTL_SESSION, data)

    async def delete_session(self, session_id: str):
        """Удалить сессию из кэша

        Args:
            session_id: ID сессии
        """
        cache_key = f"session:{session_id}"
        await self.delete(cache_key)

    # === Статистика ===

    async def get_info(self) -> Optional[Dict]:
        """Получить информацию о Redis

        Returns:
            Словарь с информацией или None
        """
        if not self.pool:
            return None
        try:
            info = await self.pool.info()
            return {
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о Redis: {e}")
            return None


# Глобальный экземпляр клиента
redis_client = RedisClient()


async def init_redis():
    """Инициализация глобального Redis клиента"""
    await redis_client.connect()


async def close_redis():
    """Закрытие глобального Redis клиента"""
    await redis_client.close()
