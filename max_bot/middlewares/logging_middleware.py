"""Middleware логирования всех входящих событий и ответов Core API."""

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger("max_bot")


def setup_logging(level: str = "INFO") -> None:
    """Базовая настройка форматирования логов."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


class LoggingMiddleware(BaseMiddleware):
    """Логирует каждое событие (message/callback) с временем обработки."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        started = time.monotonic()
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            logger.info(
                "MESSAGE from user=%s chat=%s text=%r",
                user_id,
                event.chat.id if event.chat else None,
                (event.text or "")[:120],
            )
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            logger.info(
                "CALLBACK from user=%s data=%r", user_id, (event.data or "")[:120]
            )
        try:
            result = await handler(event, data)
            return result
        finally:
            elapsed = (time.monotonic() - started) * 1000
            logger.debug("Event handled in %.1f ms", elapsed)
