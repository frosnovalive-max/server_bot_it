"""Standalone-воркер фоновых уведомлений (Этап 5 / раздел 7 ТЗ, вариант 1).

Периодически опрашивает Core API на предмет неотправленных уведомлений
(``GET /api/v1/notifications/pending``) и доставляет их пользователям в MAX.

Запуск отдельно от бота:
    python -m max_bot.notification_worker

или через docker-compose (сервис ``notification-worker``).
"""

import asyncio
import logging
import signal

from max_bot.bot import create_bot
from max_bot.core.api_client import core_api
from max_bot.middlewares.logging_middleware import setup_logging
from max_bot.services.notification_sender import NotificationSender

logger = logging.getLogger("max_bot.notification_worker")

POLL_INTERVAL = 10.0  # сек, пауза между циклами опроса (см. ТЗ, раздел 7)


async def main() -> None:
    setup_logging()
    logger.info("Notification worker starting (interval=%.1fs)", POLL_INTERVAL)

    bot = create_bot()
    sender = NotificationSender(bot)

    # Корректное завершение по SIGTERM/SIGINT (docker stop)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, sender.stop)

    try:
        await sender.run_forever(interval=POLL_INTERVAL)
    finally:
        await bot.session.close()
        await core_api.close()
        logger.info("Notification worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
