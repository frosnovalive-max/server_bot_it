"""HTTP-клиент для Core API (обертка над httpx).

Вся бизнес-логика (проверка лимитов, списание баллов, валидация статусов)
находится на стороне Core API. Бот вызывает только REST-эндпоинты и
транслирует ответы/ошибки обработчикам.
"""

import logging
from typing import Any

import httpx

from max_bot.core.config import get_settings

logger = logging.getLogger(__name__)


class CoreApiError(Exception):
    """Ошибка Core API: нетипичный HTTP-статус или сетевая проблема."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Core API error {status_code}: {detail}")


class CoreApiClient:
    """Асинхронный клиент Core API колледжа."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=settings.core_api_url,
            timeout=settings.core_api_timeout,
            headers={
                "X-API-Key": settings.core_api_key,
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Низкоуровневый запрос с маппингом ошибок
    # ------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        try:
            response = await self._client.request(method, path, json=json_body, params=params)
        except httpx.HTTPError as exc:  # сеть/таймаут
            logger.error("Core API network error on %s %s: %s", method, path, exc)
            raise CoreApiError(503, "Core API недоступен, попробуйте позже") from exc

        if response.status_code == 402:
            raise CoreApiError(402, "Недостаточно баллов")
        if response.status_code == 429:
            raise CoreApiError(429, "Превышен лимит заявок")
        if response.status_code == 403:
            raise CoreApiError(403, "Пользователь заблокирован")
        if response.status_code not in (200, 201, 204):
            detail = response.text[:500]
            logger.error("Core API %s %s -> %s: %s", method, path, response.status_code, detail)
            raise CoreApiError(response.status_code, detail)

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # Пользователи / профиль
    # ------------------------------------------------------------------
    async def upsert_user(
        self,
        max_user_id,
        first_name: str | None = None,
        name: str | None = None,
        username: str | None = None,
        raw_profile: dict | None = None,
    ) -> dict:
        """Создать/обновить пользователя в Core API (PUT /api/v1/users/{id}/profile)."""
        payload = {
            "first_name": first_name,
            "name": name,
            "username": username,
            "raw_profile": raw_profile or {},
        }
        return await self._request(
            "PUT", f"/api/v1/users/{max_user_id}/profile", json_body=payload
        )

    async def get_user_profile(self, max_user_id) -> dict:
        return await self._request("GET", f"/api/v1/users/{max_user_id}/profile")

    # ------------------------------------------------------------------
    # Справочники
    # ------------------------------------------------------------------
    async def get_ticket_types(self) -> list[dict]:
        data = await self._request("GET", "/api/v1/references/ticket-types")
        return data.get("items", data) if isinstance(data, dict) else data

    async def get_addresses(self) -> list[dict]:
        data = await self._request("GET", "/api/v1/references/addresses")
        return data.get("items", data) if isinstance(data, dict) else data

    # ------------------------------------------------------------------
    # Тикеты
    # ------------------------------------------------------------------
    async def create_ticket(
        self,
        author_max_user_id,
        type_id,
        address_id,
        title: str,
        description: str,
        cabinet: str | None = None,
    ) -> dict:
        """POST /api/v1/tickets — создание заявки.

        Возможные ответы Core API:
          {"status": "created", "ticket_number": ..., "new_balance": ...}
          {"status": "insufficient_points", "current_balance": ...}
        Ошибки 402/429/403 транслируются в CoreApiError.
        """
        payload = {
            "author_max_user_id": author_max_user_id,
            "type_id": type_id,
            "address_id": address_id,
            "cabinet": cabinet,
            "title": title,
            "description": description,
        }
        return await self._request("POST", "/api/v1/tickets", json_body=payload)

    async def get_user_tickets(self, max_user_id, status: str = "active") -> list[dict]:
        data = await self._request(
            "GET", f"/api/v1/users/{max_user_id}/tickets", params={"status": status}
        )
        return data.get("items", data) if isinstance(data, dict) else data

    async def get_ticket(self, ticket_id) -> dict:
        return await self._request("GET", f"/api/v1/tickets/{ticket_id}")

    async def add_ticket_message(self, ticket_id, author_max_user_id, text: str) -> dict:
        payload = {"author_max_user_id": author_max_user_id, "text": text}
        return await self._request(
            "POST", f"/api/v1/tickets/{ticket_id}/messages", json_body=payload
        )

    async def close_ticket(self, ticket_id, user_max_id) -> dict:
        return await self._request(
            "POST", f"/api/v1/tickets/{ticket_id}/close", json_body={"user_max_id": user_max_id}
        )

    async def cancel_ticket(self, ticket_id, user_max_id) -> dict:
        return await self._request(
            "POST", f"/api/v1/tickets/{ticket_id}/cancel", json_body={"user_max_id": user_max_id}
        )

    # ------------------------------------------------------------------
    # Уведомления (для фонового воркера)
    # ------------------------------------------------------------------
    async def get_pending_notifications(self) -> list[dict]:
        data = await self._request("GET", "/api/v1/notifications/pending")
        return data.get("items", data) if isinstance(data, dict) else data

    async def mark_notification_sent(self, notification_id) -> dict:
        return await self._request(
            "POST", f"/api/v1/notifications/{notification_id}/sent", json_body={}
        )

    async def mark_notification_failed(self, notification_id, error: str) -> dict:
        return await self._request(
            "POST",
            f"/api/v1/notifications/{notification_id}/failed",
            json_body={"error": error},
        )


# Глобальный singleton клиента (создается при импорте, закрывается при остановке)
core_api = CoreApiClient()
