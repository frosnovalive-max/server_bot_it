"""Инициализация Bot и Dispatcher для мессенджера MAX.

MAX (dev.max.ru/docs) имеет REST-API, идеологически совместимый с Telegram
Bot API:

  * POST /v3/messages   — отправка текста + inline_keyboard (callback_data)
  * GET  /v3/users/{id} — профиль пользователя MAX

Авторизация: заголовок ``Authorization: token <MAX_BOT_TOKEN>``.

Чтобы переиспользовать машинерию aiogram 3.x (FSM, middlewares, фильтры),
реализован кастомный ``MaxSession``, который транслирует вызовы методов
aiogram в эндпоинты MAX и возвращает ответы в формате
``{"ok": true, "result": ...}``.
"""

import logging
from typing import Any, Optional

import aiohttp

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage
from aiogram.methods.base import TelegramMethod, TelegramType
from aiogram.types import InlineKeyboardMarkup, ResponseBase

from max_bot.core.config import get_settings
from max_bot.core.redis_client import get_redis_pool

logger = logging.getLogger(__name__)


class MaxResponse(ResponseBase):
    """Обертка ответа MAX в формате aiogram."""

    result: Any = None


class MaxSession(BaseSession):
    """HTTP-сессия aiogram поверх REST API мессенджера MAX."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        # api-параметр базового класса не используется — все запросы
        # идут напрямую в MAX, а не в Telegram.
        super().__init__(timeout=timeout)
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Универсальный запрос к MAX
    # ------------------------------------------------------------------
    async def raw_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        token: str,
    ) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"token {token}"}
        logger.debug("MAX API -> %s %s", method, url)
        async with self.http.request(
            method, url, json=json_body, params=params, headers=headers
        ) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                logger.error("MAX API error %s on %s: %s", resp.status, url, data)
            return data if isinstance(data, dict) else {"raw": data}

    # ------------------------------------------------------------------
    # Интеграция с aiogram Bot
    # ------------------------------------------------------------------
    async def make_request(
        self, bot: Bot, method: TelegramMethod[TelegramType], token: str
    ) -> MaxResponse:
        """Трансляция метода aiogram в вызов MAX API."""
        if isinstance(method, SendMessage):
            payload: dict[str, Any] = {
                "chat_id": method.chat_id,
                "text": method.text,
            }
            if method.reply_markup and isinstance(method.reply_markup, InlineKeyboardMarkup):
                payload["inline_keyboard"] = [
                    [
                        {"text": btn.text, "callback_data": btn.callback_data or ""}
                        for btn in row
                    ]
                    for row in method.reply_markup.inline_keyboard
                ]
            data = await self.raw_request(
                "POST", "/messages", json_body=payload, token=token
            )
            body = data.get("body") or data
            message_id = body.get("message_id") or body.get("id") or 0
            # Возвращаем результат в форме, совместимой с pydantic-Message
            return MaxResponse(
                ok=True,
                result={
                    "message_id": int(message_id),
                    "date": 1,
                    "chat": {"id": int(method.chat_id), "type": "private"},
                    "from": {"id": 0, "is_bot": True, "first_name": "IT-служба"},
                    "text": method.text,
                },
            )

        logger.warning("Unsupported aiogram method for MAX session: %s", method.__name__)
        return MaxResponse(ok=True, result=None)

    async def stream_content(  # pragma: no cover
        self,
        url: str,
        headers: dict | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ):  # noqa: D102
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with self.http.get(
            url, headers=headers or {}, timeout=client_timeout
        ) as response:
            if raise_for_status:
                response.raise_for_status()
            async for chunk in response.content.iter_chunked(chunk_size):
                yield chunk


class MaxBot(Bot):
    """Bot aiogram поверх MAX REST API."""

    def __init__(self, **kwargs: Any) -> None:
        settings = get_settings()
        # aiogram требует формат telegram-токена; MAX-токен оборачивается
        # фиктивным суффиксом, валидные символы сохраняются как id-часть.
        token = self._normalize_token(settings.max_bot_token)
        session = MaxSession(base_url=settings.max_api_url)
        super().__init__(token=token, session=session, **kwargs)
        self.real_token = settings.max_bot_token
        self.max_session = session

    @staticmethod
    def _normalize_token(token: str) -> str:
        """Приводит MAX-токен к формату, проходимому валидатором aiogram.

        Реальный токен для MAX берется из настроек (self.real_token),
        этот нужен только внутреннему валидатору aiogram.
        """
        digits = "".join(ch for ch in (token or "") if ch.isdigit()) or "123456"
        secret = (token or "maxbot").replace(":", "").replace(" ", "")
        return f"{digits}:{secret}"

    # -- удобные обертки над MAX ---------------------------------------
    async def get_max_user(self, user_id: int) -> dict:
        """GET /v3/users/{user_id} — профиль пользователя из MAX."""
        data = await self.max_session.raw_request(
            "GET", f"/users/{user_id}", token=self.real_token
        )
        body = data.get("body") or data
        return body.get("user") or body

    async def answer_callback(self, callback_id: str) -> None:
        """Подтверждение обработки callback (чтобы у клиента «пропелась» кнопка)."""
        await self.max_session.raw_request(
            "POST", f"/messages/answer-callback?callback_id={callback_id}",
            json_body={}, token=self.real_token,
        )


def create_bot() -> MaxBot:
    return MaxBot()


def create_dispatcher():
    """Dispatcher с RedisStorage — состояния многошаговых диалогов в Redis."""
    from aiogram import Dispatcher
    from aiogram.fsm.storage.redis import RedisStorage

    from max_bot.handlers.errors import register_error_handlers
    from max_bot.middlewares.logging_middleware import LoggingMiddleware

    redis = get_redis_pool()
    storage = RedisStorage(redis)
    dp = Dispatcher(storage=storage)
    dp.message.outer_middleware(LoggingMiddleware())
    dp.callback_query.outer_middleware(LoggingMiddleware())
    register_error_handlers(dp)
    return dp
