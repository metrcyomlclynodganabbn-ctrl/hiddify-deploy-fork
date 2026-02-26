"""Cache модуль для кэширования данных"""

from .redis_client import RedisClient, redis_client, init_redis, close_redis

__all__ = [
    'RedisClient',
    'redis_client',
    'init_redis',
    'close_redis'
]
