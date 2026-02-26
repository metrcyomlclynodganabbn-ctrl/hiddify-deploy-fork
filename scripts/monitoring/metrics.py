"""
Prometheus метрики для мониторинга бота

Модуль предоставляет метрики для мониторинга работы бота:
- Счётчики сообщений, конфигов, ошибок
- Histograms для измерения времени обработки
- Gauges для активных пользователей

Требования:
- pip install prometheus-client
"""

import os
import time
import logging
from typing import Optional
from functools import wraps

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """Контейнер для Prometheus метрик"""

    def __init__(self, port: int = 9090):
        """Инициализация метрик

        Args:
            port: Порт для metrics endpoint
        """
        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client не установлен")
            return

        self.port = port
        self._started = False

        # Счётчики
        self.messages_total = Counter(
            'telegram_bot_messages_total',
            'Total messages received',
            ['user_id', 'message_type']
        )

        self.configs_generated = Counter(
            'telegram_bot_configs_generated_total',
            'Total configs generated',
            ['mode']  # standard, enhanced
        )

        self.payments_created = Counter(
            'telegram_bot_payments_created_total',
            'Total payments created',
            ['provider', 'currency']
        )

        self.payments_completed = Counter(
            'telegram_bot_payments_completed_total',
            'Total payments completed',
            ['provider', 'currency']
        )

        self.tickets_created = Counter(
            'telegram_bot_tickets_created_total',
            'Total support tickets created',
            ['category']
        )

        self.referrals_created = Counter(
            'telegram_bot_referrals_total',
            'Total referrals created'
        )

        self.errors_total = Counter(
            'telegram_bot_errors_total',
            'Total errors',
            ['error_type', 'handler']
        )

        # Histograms
        self.message_processing_duration = Histogram(
            'telegram_bot_message_processing_seconds',
            'Message processing duration',
            ['handler'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        self.api_request_duration = Histogram(
            'telegram_bot_api_request_seconds',
            'API request duration',
            ['endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        # Gauges
        self.active_users = Gauge(
            'telegram_bot_active_users',
            'Active users (DAU)'
        )

        self.online_users = Gauge(
            'telegram_bot_online_users',
            'Online users (last 5 minutes)'
        )

        self.database_connections = Gauge(
            'telegram_bot_db_connections',
            'Active database connections'
        )

        self.cache_hit_rate = Gauge(
            'telegram_bot_cache_hit_rate',
            'Cache hit rate (0-1)'
        )

        self.queue_size = Gauge(
            'telegram_bot_queue_size',
            'Current queue size'
        )

    async def start_server(self):
        """Запустить HTTP сервер для метрик

        Returns:
            True если сервер запущен
        """
        if not PROMETHEUS_AVAILABLE:
            return False

        if self._started:
            return True

        try:
            start_http_server(self.port)
            self._started = True
            logger.info(f"Prometheus metrics endpoint запущен на порту {self.port}")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска Prometheus сервера: {e}")
            return False

    def track_message(self, user_id: int, message_type: str):
        """Записать метрику сообщения

        Args:
            user_id: ID пользователя
            message_type: Тип сообщения
        """
        if PROMETHEUS_AVAILABLE:
            self.messages_total.labels(
                user_id=str(user_id),
                message_type=message_type
            ).inc()

    def track_config_generated(self, mode: str):
        """Записать метрику генерации конфига

        Args:
            mode: Режим (standard/enhanced)
        """
        if PROMETHEUS_AVAILABLE:
            self.configs_generated.labels(mode=mode).inc()

    def track_payment_created(self, provider: str, currency: str):
        """Записать метрику создания платежа

        Args:
            provider: Провайдер
            currency: Код валюты
        """
        if PROMETHEUS_AVAILABLE:
            self.payments_created.labels(provider=provider, currency=currency).inc()

    def track_payment_completed(self, provider: str, currency: str):
        """Записать метрику завершения платежа

        Args:
            provider: Провайдер
            currency: Код валюты
        """
        if PROMETHEUS_AVAILABLE:
            self.payments_completed.labels(provider=provider, currency=currency).inc()

    def track_ticket_created(self, category: str):
        """Записать метрику создания тикета

        Args:
            category: Категория тикета
        """
        if PROMETHEUS_AVAILABLE:
            self.tickets_created.labels(category=category).inc()

    def track_error(self, error_type: str, handler: str):
        """Записать метрику ошибки

        Args:
            error_type: Тип ошибки
            handler: Обработчик
        """
        if PROMETHEUS_AVAILABLE:
            self.errors_total.labels(error_type=error_type, handler=handler).inc()

    def track_referral_created(self):
        """Записать метрику создания реферала"""
        if PROMETHEUS_AVAILABLE:
            self.referrals_created.inc()

    def set_active_users(self, count: int):
        """Установить количество активных пользователей

        Args:
            count: Количество пользователей
        """
        if PROMETHEUS_AVAILABLE:
            self.active_users.set(count)

    def set_online_users(self, count: int):
        """Установить количество онлайн пользователей

        Args:
            count: Количество пользователей
        """
        if PROMETHEUS_AVAILABLE:
            self.online_users.set(count)

    def set_db_connections(self, count: int):
        """Установить количество соединений с БД

        Args:
            count: Количество соединений
        """
        if PROMETHEUS_AVAILABLE:
            self.database_connections.set(count)

    def set_cache_hit_rate(self, rate: float):
        """Установить命中率 кэша

        Args:
            rate: Hit rate (0-1)
        """
        if PROMETHEUS_AVAILABLE:
            self.cache_hit_rate.set(rate)

    def set_queue_size(self, size: int):
        """Установить размер очереди

        Args:
            size: Размер очереди
        """
        if PROMETHEUS_AVAILABLE:
            self.queue_size.set(size)


def track_message_duration(handler_name: str = None):
    """Декоратор для отслеживания времени обработки сообщения

    Args:
        handler_name: Имя обработчика

    Returns:
        Декоратор
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not PROMETHEUS_AVAILABLE:
                return await func(*args, **kwargs)

            start_time = time.time()
            handler = handler_name or func.__name__

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                metrics.message_processing_duration.labels(handler=handler).observe(duration)

        return wrapper
    return decorator


def track_api_request(endpoint: str = None):
    """Декоратор для отслеживания времени API запроса

    Args:
        endpoint: Имя эндпоинта

    Returns:
        Декоратор
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not PROMETHEUS_AVAILABLE:
                return await func(*args, **kwargs)

            start_time = time.time()
            ep = endpoint or func.__name__

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                metrics.api_request_duration.labels(endpoint=ep).observe(duration)

        return wrapper
    return decorator


# Глобальный экземпляр
metrics = PrometheusMetrics(
    port=int(os.getenv('METRICS_PORT', '9090'))
)


async def init_metrics():
    """Инициализация метрик"""
    await metrics.start_server()


def get_metrics() -> PrometheusMetrics:
    """Получить экземпляр метрик

    Returns:
        PrometheusMetrics
    """
    return metrics
