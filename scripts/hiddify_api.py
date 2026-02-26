#!/usr/bin/env python3
"""
Hiddify Manager API Client
Клиент для работы с Hiddify Manager API
"""

import os
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class HiddifyAPIError(Exception):
    """Базовое исключение для ошибок Hiddify API"""
    pass


class HiddifyAPIConnectionError(HiddifyAPIError):
    """Ошибка подключения к API"""
    pass


class HiddifyAPIAuthError(HiddifyAPIError):
    """Ошибка аутентификации"""
    pass


class HiddifyAPI:
    """Клиент для Hiddify Manager API

    Документация: https://github.com/hiddify/Hiddify-Manager/wiki/API
    """

    def __init__(self, base_url: str = None, token: str = None, timeout: int = 10):
        """Инициализация API клиента

        Args:
            base_url: Базовый URL API (например: https://panel.example.com/api)
            token: API токен для аутентификации
            timeout: Таймаут запросов в секундах
        """
        self.base_url = base_url or os.getenv('PANEL_DOMAIN', '')
        # Добавляем /api если отсутствует
        if self.base_url and not self.base_url.endswith('/api'):
            if self.base_url.endswith('/'):
                self.base_url += 'api'
            else:
                self.base_url += '/api'

        self.token = token or os.getenv('HIDDIFY_API_TOKEN', '')
        self.timeout = timeout

        if not self.base_url:
            logger.warning("PANEL_DOMAIN не установлен")
        if not self.token:
            logger.warning("HIDDIFY_API_TOKEN не установлен")

    @property
    def headers(self) -> Dict[str, str]:
        """Заголовки для API запросов"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Выполнить запрос к API

        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: Эндпоинт API
            **kwargs: Дополнительные аргументы для requests

        Returns:
            Dict с ответом от API

        Raises:
            HiddifyAPIConnectionError: Ошибка сети
            HiddifyAPIAuthError: Ошибка аутентификации
            HiddifyAPIError: Прочие ошибки API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=self.timeout,
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

        except requests.exceptions.Timeout:
            raise HiddifyAPIConnectionError(f"Таймаут подключения к {url}")
        except requests.exceptions.ConnectionError as e:
            raise HiddifyAPIConnectionError(f"Ошибка подключения: {e}")
        except requests.exceptions.RequestException as e:
            raise HiddifyAPIError(f"Ошибка запроса: {e}")

    # ========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ
    # ========================================================================

    def create_user(self, username: str, data_limit_gb: int = 100,
                    expire_days: int = 30, protocols: List[str] = None) -> Dict:
        """Создать нового пользователя

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
        result = self._request("POST", "/users", json=payload)

        return result

    def get_users(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Получить список пользователей

        Args:
            limit: Максимальное количество пользователей
            offset: Смещение для пагинации

        Returns:
            List[Dict] с данными пользователей
        """
        params = {"limit": limit, "offset": offset}
        result = self._request("GET", "/users", params=params)

        return result.get("users", result)  # Обработка разных форматов ответа

    def get_user(self, user_uuid: str) -> Dict:
        """Получить данные пользователя по UUID

        Args:
            user_uuid: UUID пользователя

        Returns:
            Dict с данными пользователя
        """
        result = self._request("GET", f"/users/{user_uuid}")
        return result

    def update_user(self, user_uuid: str, **kwargs) -> Dict:
        """Обновить данные пользователя

        Args:
            user_uuid: UUID пользователя
            **kwargs: Поля для обновления (data_limit, expire_days, etc.)

        Returns:
            Dict с обновленными данными
        """
        result = self._request("PUT", f"/users/{user_uuid}", json=kwargs)
        return result

    def delete_user(self, user_uuid: str) -> Dict:
        """Удалить пользователя

        Args:
            user_uuid: UUID пользователя

        Returns:
            Dict с результатом удаления
        """
        result = self._request("DELETE", f"/users/{user_uuid}")
        return result

    def get_user_connections(self, user_uuid: str) -> List[Dict]:
        """Получить активные подключения пользователя

        Args:
            user_uuid: UUID пользователя

        Returns:
            List[Dict] с данными о подключениях
        """
        try:
            result = self._request("GET", f"/users/{user_uuid}/connections")
            return result.get("connections", [])
        except HiddifyAPIError:
            # Если эндпоинт не поддерживается, возвращаем пустой список
            logger.warning(f"Эндпоинт /users/{user_uuid}/connections не поддерживается")
            return []

    # ========================================================================
    # МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ СТАТИСТИКИ
    # ========================================================================

    def get_stats(self) -> Dict:
        """Получить статистику системы

        Returns:
            Dict со статистикой:
                - today_traffic: Трафик за сегодня
                - month_traffic: Трафик за месяц
                - total_users: Всего пользователей
                - active_users: Активных пользователей
        """
        try:
            result = self._request("GET", "/stats")
            return result
        except HiddifyAPIError as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}

    def get_system_health(self) -> Dict:
        """Проверить здоровье системы

        Returns:
            Dict с информацией о здоровье системы
        """
        try:
            result = self._request("GET", "/health")
            return result
        except HiddifyAPIError as e:
            logger.error(f"Ошибка проверки здоровья: {e}")
            return {"status": "unhealthy", "error": str(e)}

    # ========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ========================================================================

    def test_connection(self) -> bool:
        """Проверить подключение к API

        Returns:
            True если подключение успешно, иначе False
        """
        try:
            self.get_system_health()
            return True
        except HiddifyAPIError:
            return False

    def get_subscription_link(self, user_uuid: str) -> str:
        """Получить ссылку на подписку пользователя

        Args:
            user_uuid: UUID пользователя

        Returns:
            Ссылка на подписку
        """
        base_domain = self.base_url.replace('/api', '')
        return f"{base_domain}/{user_uuid}"


# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ИНВАЙТАМИ
# ============================================================================

def validate_invite_code(db_path: str, invite_code: str) -> Optional[Dict]:
    """Проверить валидность инвайт-кода в БД

    Унифицированные проверки соответствуют условиям в use_invite_code():
    - Код активен (is_active = 1)
    - Срок действия не истёк (expires_at > NOW или NULL)
    - Лимит использований не достигнут (used_count < max_uses)

    Args:
        db_path: Путь к базе данных
        invite_code: Код инвайта

    Returns:
        Dict с данными инвайта если валиден, иначе None
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT id, code, created_by, created_at, expires_at,
                   max_uses, used_count, is_active
            FROM invites
            WHERE code = ? AND is_active = 1
            AND (expires_at IS NULL OR expires_at > datetime('now'))
            AND used_count < max_uses
        ''', (invite_code,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def use_invite_code(db_path: str, invite_code: str) -> dict:
    """Атомарное использование инвайт-кода с проверкой лимита

    Использует атомарный UPDATE с проверкой всех условий в одном запросе,
    что предотвращает race condition при параллельных запросах.

    Args:
        db_path: Путь к базе данных
        invite_code: Код инвайта

    Returns:
        dict с результатом операции:
            - success: bool - успешно ли использован
            - message: str - сообщение о результате
            - invite_data: dict|None - данные инвайта (если успешно)
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Атомарная проверка и обновление в одном запросе
        cursor.execute('''
            UPDATE invites
            SET used_count = used_count + 1,
                is_active = CASE
                    WHEN used_count + 1 >= max_uses THEN 0
                    ELSE is_active
                END
            WHERE code = ?
                AND is_active = 1
                AND (expires_at IS NULL OR expires_at > datetime('now'))
                AND used_count < max_uses
        ''', (invite_code,))

        if cursor.rowcount == 0:
            return {
                'success': False,
                'message': 'Инвайт-код недействителен, истёк или исчерпан',
                'invite_data': None
            }

        # Получить обновлённые данные
        cursor.execute('''
            SELECT id, code, created_by, created_at, expires_at,
                   max_uses, used_count, is_active
            FROM invites WHERE code = ?
        ''', (invite_code,))

        result = cursor.fetchone()
        columns = ['id', 'code', 'created_by', 'created_at', 'expires_at',
                   'max_uses', 'used_count', 'is_active']

        conn.commit()

        return {
            'success': True,
            'message': 'Инвайт-код использован',
            'invite_data': dict(zip(columns, result))
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка использования инвайта: {e}")
        return {
            'success': False,
            'message': f'Ошибка: {e}',
            'invite_data': None
        }
    finally:
        conn.close()


def create_invite_code(db_path: str, code: str, created_by: int,
                      max_uses: int = 1, expires_at: str = None) -> dict:
    """Создать инвайт-код с валидацией параметров

    Валидация включает:
    - Проверка формата кода (должен начинаться с INV_)
    - Проверка длины кода (8-50 символов)
    - Проверка диапазона max_uses (1-1000)
    - Проверка существования создателя
    - Проверка срока действия (не в прошлом)

    Args:
        db_path: Путь к базе данных
        code: Код инвайта (формат INV_xxxxx)
        created_by: Telegram ID создателя
        max_uses: Максимальное количество использований (1-1000)
        expires_at: Дата истечения (ISO формат, опционально)

    Returns:
        dict с результатом операции:
            - success: bool - успешно ли создан
            - message: str - сообщение о результате
            - invite_data: dict|None - данные инвайта (если успешно)
    """
    import sqlite3
    from datetime import datetime

    # Валидация параметров
    try:
        if max_uses < 1 or max_uses > 1000:
            return {
                'success': False,
                'message': 'max_uses должен быть от 1 до 1000',
                'invite_data': None
            }

        if not code.startswith('INV_'):
            return {
                'success': False,
                'message': 'Код должен начинаться с INV_',
                'invite_data': None
            }

        if len(code) < 8 or len(code) > 50:
            return {
                'success': False,
                'message': 'Длина кода должна быть от 8 до 50 символов',
                'invite_data': None
            }

        # Проверить created_by существует (по telegram_id)
        conn_check = sqlite3.connect(db_path)
        cursor_check = conn_check.cursor()
        cursor_check.execute('SELECT id FROM users WHERE telegram_id = ?', (created_by,))
        if not cursor_check.fetchone():
            conn_check.close()
            return {
                'success': False,
                'message': f'Пользователь-создатель (telegram_id={created_by}) не существует',
                'invite_data': None
            }
        conn_check.close()

        # Проверить expires_at
        expiry_dt = None
        if expires_at:
            try:
                expiry_dt = datetime.fromisoformat(expires_at)
                if expiry_dt < datetime.now():
                    return {
                        'success': False,
                        'message': 'Срок действия не может быть в прошлом',
                        'invite_data': None
                    }
            except ValueError:
                return {
                    'success': False,
                    'message': 'Некорректный формат даты (используйте ISO формат)',
                    'invite_data': None
                }

    except Exception as e:
        return {
            'success': False,
            'message': f'Ошибка валидации: {e}',
            'invite_data': None
        }

    # Создать инвайт
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO invites (code, created_by, max_uses, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (code, created_by, max_uses, expires_at))

        conn.commit()

        # Получить созданный инвайт
        cursor.execute('''
            SELECT id, code, created_by, created_at, expires_at,
                   max_uses, used_count, is_active
            FROM invites WHERE code = ?
        ''', (code,))

        result = cursor.fetchone()
        columns = ['id', 'code', 'created_by', 'created_at', 'expires_at',
                   'max_uses', 'used_count', 'is_active']

        return {
            'success': True,
            'message': 'Инвайт-код создан',
            'invite_data': dict(zip(columns, result))
        }

    except sqlite3.IntegrityError:
        return {
            'success': False,
            'message': f'Инвайт-код {code} уже существует',
            'invite_data': None
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Ошибка создания инвайта: {e}',
            'invite_data': None
        }
    finally:
        conn.close()
