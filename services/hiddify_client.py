"""
Async Hiddify Manager API Client.
Асинхронная обёртка над Hiddify Manager API используя httpx.

Документация: https://github.com/hiddify/Hiddify-Manager/wiki/API
"""

import logging
from typing import Dict, List, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class HiddifyAPIError(Exception):
    """Базовое исключение для ошибок Hiddify API"""
    pass


class HiddifyAPIConnectionError(HiddifyAPIError):
    """Ошибка подключения к API"""
    pass


class HiddifyAPIAuthError(HiddifyAPIError):
    """Ошибка аутентификации"""
    pass


# ============================================================================
# ASYNC HIDDIfy API CLIENT
# ============================================================================

class AsyncHiddifyAPI:
    """
    Асинхронный клиент для Hiddify Manager API.

    Заменяет синхронный requests клиент на httpx.AsyncClient.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Инициализация API клиента.

        Args:
            base_url: Базовый URL API (например: https://panel.example.com/api)
            token: API токен для аутентификации
            timeout: Таймаут запросов в секундах
        """
        self.base_url = base_url or settings.hiddify_api_url
        self.token = token or settings.hiddify_api_token
        self.timeout = timeout

        self._client: Optional[httpx.AsyncClient] = None

        if not self.base_url:
            logger.warning("HIDDIFY_API_URL не установлен")
        if not self.token:
            logger.warning("HIDDIFY_API_TOKEN не установлен")

    @property
    def headers(self) -> Dict[str, str]:
        """Заголовки для API запросов"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client for API requests.

        Returns:
            httpx.AsyncClient: Async HTTP client
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                verify=False,  # For self-signed certificates
            )
            logger.debug("HTTP client created")
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("HTTP client closed")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict:
        """
        Выполнить запрос к API.

        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: Эндпоинт API
            **kwargs: Дополнительные аргументы для httpx

        Returns:
            Dict с ответом от API

        Raises:
            HiddifyAPIConnectionError: Ошибка сети
            HiddifyAPIAuthError: Ошибка аутентификации
            HiddifyAPIError: Прочие ошибки API
        """
        client = await self.get_client()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                **kwargs
            )

            # Проверка аутентификации
            if response.status_code == 401:
                raise HiddifyAPIAuthError("Неверный API токен")

            # Проверка других ошибок
            if response.status_code >= 400:
                error_msg = response.text or f"HTTP {response.status_code}"
                raise HiddifyAPIError(f"API Error: {error_msg}")

            return response.json()

        except httpx.TimeoutException:
            raise HiddifyAPIConnectionError(f"Таймаут подключения к {url}")
        except httpx.ConnectError as e:
            raise HiddifyAPIConnectionError(f"Ошибка подключения: {e}")
        except httpx.HTTPError as e:
            raise HiddifyAPIError(f"Ошибка запроса: {e}")

    # ========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ
    # ========================================================================

    async def create_user(
        self,
        username: str,
        data_limit_gb: int = 100,
        expire_days: int = 30,
        protocols: Optional[List[str]] = None
    ) -> Dict:
        """
        Создать нового пользователя в Hiddify.

        Args:
            username: Имя пользователя
            data_limit_gb: Лимит трафика в GB
            expire_days: Срок действия в днях
            protocols: Список протоколов (по умолчанию: vless_reality, hysteria2, ss2022)

        Returns:
            Dict с данными созданного пользователя:
                - uuid: UUID пользователя
                - subscription_link: Ссылка на подписку
                - и другие поля...
        """
        if protocols is None:
            protocols = ["vless_reality", "hysteria2", "shadowsocks2022"]

        payload = {
            "username": username,
            "data_limit": data_limit_gb * 1024**3,  # Конвертация в байты
            "expire_days": expire_days,
            "protocols": protocols
        }

        logger.info(f"Создание пользователя: {username}")
        result = await self._request("POST", "/users", json=payload)

        return result

    async def get_users(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Получить список пользователей.

        Args:
            limit: Максимальное количество пользователей
            offset: Смещение для пагинации

        Returns:
            List[Dict] с данными пользователей
        """
        params = {"limit": limit, "offset": offset}
        result = await self._request("GET", "/users", params=params)

        # Обработка разных форматов ответа
        return result.get("users", result) if isinstance(result, dict) else result

    async def get_user(self, user_uuid: str) -> Dict:
        """
        Получить данные пользователя по UUID.

        Args:
            user_uuid: UUID пользователя

        Returns:
            Dict с данными пользователя
        """
        result = await self._request("GET", f"/users/{user_uuid}")
        return result

    async def update_user(
        self,
        user_uuid: str,
        **kwargs
    ) -> Dict:
        """
        Обновить данные пользователя.

        Args:
            user_uuid: UUID пользователя
            **kwargs: Поля для обновления (data_limit, expire_days, etc.)

        Returns:
            Dict с обновленными данными
        """
        result = await self._request("PUT", f"/users/{user_uuid}", json=kwargs)
        return result

    async def delete_user(self, user_uuid: str) -> Dict:
        """
        Удалить пользователя.

        Args:
            user_uuid: UUID пользователя

        Returns:
            Dict с результатом удаления
        """
        result = await self._request("DELETE", f"/users/{user_uuid}")
        return result

    async def get_user_connections(self, user_uuid: str) -> List[Dict]:
        """
        Получить активные подключения пользователя.

        Args:
            user_uuid: UUID пользователя

        Returns:
            List[Dict] с данными о подключениях
        """
        try:
            result = await self._request("GET", f"/users/{user_uuid}/connections")
            return result.get("connections", [])
        except HiddifyAPIError:
            # Если эндпоинт не поддерживается, возвращаем пустой список
            logger.warning(f"Эндпоинт /users/{user_uuid}/connections не поддерживается")
            return []

    # ========================================================================
    # МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ СТАТИСТИКИ
    # ========================================================================

    async def get_stats(self) -> Dict:
        """
        Получить статистику системы.

        Returns:
            Dict со статистикой:
                - today_traffic: Трафик за сегодня
                - month_traffic: Трафик за месяц
                - total_users: Всего пользователей
                - active_users: Активных пользователей
        """
        try:
            result = await self._request("GET", "/stats")
            return result
        except HiddifyAPIError as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}

    async def get_system_health(self) -> Dict:
        """
        Проверить здоровье системы.

        Returns:
            Dict с информацией о здоровье системы
        """
        try:
            result = await self._request("GET", "/health")
            return result
        except HiddifyAPIError as e:
            logger.error(f"Ошибка проверки здоровья: {e}")
            return {"status": "unhealthy", "error": str(e)}

    # ========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ========================================================================

    async def test_connection(self) -> bool:
        """
        Проверить подключение к API.

        Returns:
            True если подключение успешно, иначе False
        """
        try:
            await self.get_system_health()
            return True
        except HiddifyAPIError:
            return False

    async def get_subscription_link(self, user_uuid: str) -> str:
        """
        Получить ссылку на подписку пользователя.

        Args:
            user_uuid: UUID пользователя

        Returns:
            Ссылка на подписку
        """
        # Убираем /api из base_url если есть
        base_domain = self.base_url.replace('/api', '')
        return f"{base_domain}/{user_uuid}"

    # ========================================================================
    # КОНТЕКСТНЫЙ МЕНЕДЖЕР
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================================

# Глобальный клиент для использования в приложении
_hiddify_client: Optional[AsyncHiddifyAPI] = None


def get_hiddify_client() -> AsyncHiddifyAPI:
    """
    Получить глобальный экземпляр Hiddify API клиента.

    Returns:
        AsyncHiddifyAPI: Экземпляр API клиента
    """
    global _hiddify_client
    if _hiddify_client is None:
        _hiddify_client = AsyncHiddifyAPI()
        logger.info("Global Hiddify client created")
    return _hiddify_client


async def close_hiddify_client() -> None:
    """Закрыть глобальный клиент."""
    global _hiddify_client
    if _hiddify_client:
        await _hiddify_client.close()
        _hiddify_client = None
        logger.info("Global Hiddify client closed")


__all__ = [
    "AsyncHiddifyAPI",
    "HiddifyAPIError",
    "HiddifyAPIConnectionError",
    "HiddifyAPIAuthError",
    "get_hiddify_client",
    "close_hiddify_client",
]
