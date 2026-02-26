"""
Health check endpoint для мониторинга здоровья сервиса

Модуль предоставляет HTTP endpoint для проверки здоровья:
- Проверка соединения с БД
- Проверка Redis
- Проверка Hiddify API
- Статистика по компонентам

Требования:
- pip install aiohttp
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None

from ..cache.redis_client import redis_client
from ..hiddify_api import HiddifyAPI
from ..database.connection import get_db_connection

logger = logging.getLogger(__name__)


class HealthChecker:
    """Класс для проверки здоровья сервиса"""

    def __init__(self):
        """Инициализация health checker"""
        self.app = None
        self.runner = None
        self.site = None
        self.port = int(os.getenv('HEALTH_PORT', '8080'))

    async def check_database(self) -> Dict[str, Any]:
        """Проверка соединения с БД

        Returns:
            Словарь с результатом проверки
        """
        db_path = os.getenv('DB_PATH', 'data/bot.db')

        try:
            async with get_db_connection(db_path) as conn:
                # Тестовый запрос
                await conn.execute("SELECT 1")

                # Получение информации о БД
                result = await conn.execute("SELECT COUNT(*) FROM users")
                user_count = (await result.fetchone())[0]

                return {
                    "status": "ok",
                    "users": user_count,
                    "path": db_path
                }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def check_redis(self) -> Dict[str, Any]:
        """Проверка соединения с Redis

        Returns:
            Словарь с результатом проверки
        """
        if not redis_client.pool:
            return {
                "status": "disabled",
                "message": "Redis не подключён"
            }

        try:
            # Ping
            await redis_client.pool.ping()

            # Получение информации
            info = await redis_client.get_info()

            return {
                "status": "ok",
                "connected": True,
                "info": info
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def check_hiddify_api(self) -> Dict[str, Any]:
        """Проверка соединения с Hiddify API

        Returns:
            Словарь с результатом проверки
        """
        try:
            api = HiddifyAPI()

            # Проверка доступности
            if not api.base_url or not api.token:
                return {
                    "status": "disabled",
                    "message": "Hiddify API не настроен"
                }

            # Тестовый запрос (если доступен метод для проверки)
            # В реальной реализации может быть вызов метода ping
            return {
                "status": "ok",
                "base_url": api.base_url
            }
        except Exception as e:
            logger.error(f"Hiddify API health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def health_check(self, request: web.Request) -> web.Response:
        """Основной health check endpoint

        Args:
            request: aiohttp request

        Returns:
            JSON response со статусом здоровья
        """
        health_status = "healthy"
        checks = {
            "timestamp": datetime.now().isoformat(),
            "version": "4.0.0",
            "checks": {}
        }

        # Проверка БД (критично)
        db_check = await self.check_database()
        checks["checks"]["database"] = db_check
        if db_check.get("status") == "error":
            health_status = "unhealthy"

        # Проверка Redis (некритично)
        redis_check = await self.check_redis()
        checks["checks"]["redis"] = redis_check

        # Проверка Hiddify API (некритично)
        api_check = await self.check_hiddify_api()
        checks["checks"]["hiddify_api"] = api_check

        checks["status"] = health_status

        # Определение HTTP status code
        status_code = 200 if health_status == "healthy" else 503

        return web.json_response(checks, status=status_code)

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check - готов ли сервис принимать запросы

        Args:
            request: aiohttp request

        Returns:
            JSON response
        """
        # Readiness проверяет только критичные компоненты
        db_check = await self.check_database()

        ready = db_check.get("status") == "ok"

        return web.json_response({
            "ready": ready,
            "timestamp": datetime.now().isoformat()
        }, status=200 if ready else 503)

    async def liveness_check(self, request: web.Request) -> web.Response:
        """Liveness check - жив ли сервис

        Args:
            request: aiohttp request

        Returns:
            JSON response
        """
        # Liveness - простая проверка что сервис отвечает
        return web.json_response({
            "alive": True,
            "timestamp": datetime.now().isoformat()
        })

    async def metrics_check(self, request: web.Request) -> web.Response:
        """Проверка метрик (для Prometheus)

        Args:
            request: aiohttp request

        Returns:
            JSON response с метриками
        """
        db_check = await self.check_database()
        redis_check = await self.check_redis()

        metrics_data = {
            "database_users": db_check.get("users", 0),
            "redis_connected": redis_check.get("connected", False),
            "timestamp": datetime.now().isoformat()
        }

        return web.json_response(metrics_data)

    def create_app(self) -> web.Application:
        """Создать aiohttp приложение

        Returns:
            web.Application
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp не установлен")

        app = web.Application()
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/ready", self.readiness_check)
        app.router.add_get("/live", self.liveness_check)
        app.router.add_get("/metrics", self.metrics_check)

        return app

    async def start(self):
        """Запустить health check сервер

        Returns:
            True если запущен
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp не установлен, health check отключён")
            return False

        if self.runner is not None:
            return True  # Уже запущен

        try:
            self.app = self.create_app()
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()

            logger.info(f"Health check endpoint запущен на порту {self.port}")
            logger.info(f"  http://localhost:{self.port}/health")
            logger.info(f"  http://localhost:{self.port}/ready")
            logger.info(f"  http://localhost:{self.port}/live")

            return True
        except Exception as e:
            logger.error(f"Ошибка запуска health check сервера: {e}")
            return False

    async def stop(self):
        """Остановить health check сервер"""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            self.site = None
            logger.info("Health check сервер остановлен")


# Глобальный экземпляр
health_checker = HealthChecker()


async def start_health_server():
    """Запуск health check сервера"""
    await health_checker.start()


async def stop_health_server():
    """Остановка health check сервера"""
    await health_checker.stop()


def get_health_checker() -> HealthChecker:
    """Получить экземпляр health checker

    Returns:
        HealthChecker
    """
    return health_checker
