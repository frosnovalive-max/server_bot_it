"""Фоновая отправка уведомлений пользователям MAX.

Вариант 1 из ТЗ: периодический опрос Core API за неотправленными
уведомлениями (см. notification_worker.py для standalone-режима).
"""

import asyncio
import logging

from max_bot.core.api_client import CoreApiError, core_api

logger = logging.getLogger(__name__)


class NotificationSender:
    """Отправляет уведомления из очереди Core API в MAX."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._task: asyncio.Task | None = None
        self._running = False

    async def send_one(self, notif: dict) -> None:
        user_id = notif["user_max_id"]
        text = notif["message"]
        try:
            await self.bot.send_message(chat_id=int(user_id), text=text)
            await core_api.mark_notification_sent(notif["id"])
            logger.info("Notification %s sent to user %s", notif["id"], user_id)
        except Exception as exc:
            logger.error("Failed to send notification %s: %s", notif.get("id"), exc)
            try:
                await core_api.mark_notification_failed(notif["id"], str(exc))
            except CoreApiError:
                logger.exception("Cannot mark notification %s failed", notif.get("id"))

    async def poll_once(self) -> int:
        """Один цикл опроса. Возвращает число обработанных уведомлений."""
        notifications = await core_api.get_pending_notifications()
        for notif in notifications:
            await self.send_one(notif)
        return len(notifications)

    async def run_forever(self, interval: float = 10.0) -> None:
        """Бесконечный цикл опроса (для standalone worker)."""
        self._running = True
        while self._running:
            try:
                count = await self.poll_once()
                if count:
                    logger.info("Processed %d pending notifications", count)
            except CoreApiError as exc:
                logger.warning("Notification poll skipped, Core API error: %s", exc)
            except Exception:
                logger.exception("Unexpected error in notification loop")
            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
