"""Точка входа: webhook-сервер для приема событий от мессенджера MAX.

MAX (dev.max.ru) доставляет события в формате JSON по HTTP POST на путь
/webhook/max. Формат update'а MAX отличается от Telegram, поэтому здесь
реализован адаптер, который конвертирует событие MAX во внутреннюю
структуру и передает его диспетчеру бота.

Запуск:  python -m max_bot.main   (или uvicorn в docker-compose)
"""

import asyncio
import logging
import secrets

from aiohttp import web

from max_bot.core.config import get_settings
from max_bot.handlers import setup_routers
from max_bot.middlewares.logging_middleware import setup_logging
from max_bot.bot import create_bot, create_dispatcher

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Адаптер формата MAX -> внутренние события бота
# ---------------------------------------------------------------------------
def extract_update_type(payload: dict) -> str:
    """Определяет тип события из payload вебхука MAX."""
    if "update_type" in payload:
        return payload["update_type"]
    body = payload.get("body") or {}
    if "message" in body:
        return "message_new"
    if "callback" in body:
        return "message_callback"
    if "user" in body and payload.get("type") == "user_joined":
        return "user_joined"
    return payload.get("event", "unknown")


async def handle_max_webhook(request: web.Request) -> web.Response:
    """POST /webhook/max — прием вебхуков от MAX."""
    # Проверка секрета вебхука (если задан)
    if settings.secret_token:
        received = request.headers.get("X-Max-Webhook-Secret", "")
        if not secrets.compare_digest(received, settings.secret_token):
            logger.warning("Webhook rejected: bad secret token from %s", request.remote)
            return web.json_response({"error": "invalid secret"}, status=401)

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    update_type = extract_update_type(payload)
    logger.info("Incoming MAX webhook: %s", update_type)

    dispatcher = request.app["dispatcher"]
    try:
        # MAX ожидает быстрый ответ (200), обработка feed'ом fp в фоне допустима,
        # но синхронная обработка проще для отладки — ждем завершения.
        await dispatcher.feed_update(bot=request.app["bot"], update=payload)
    except Exception:
        logger.exception("Failed to process MAX webhook update")

    return web.json_response({"status": "ok"})


async def handle_health(_request: web.Request) -> web.Response:
    """GET /healthz — проверка живости для Docker/orchestrator."""
    return web.json_response({"status": "ok"})


# ---------------------------------------------------------------------------
# Регистрация/снятие вебхука в MAX API (опционально, при наличии токена)
# ---------------------------------------------------------------------------
async def maybe_set_webhook(bot) -> None:
    if settings.webhook_url:
        try:
            await bot.request(
                "POST",
                f"/setWebhook?url={settings.webhook_url}",
            )
            logger.info("Webhook registered in MAX: %s", settings.webhook_url)
        except Exception as exc:
            logger.warning("Could not register webhook in MAX: %s", exc)


async def on_startup(app: web.Application) -> None:
    await maybe_set_webhook(app["bot"])
    logger.info("Bot started, listening %s:%s%s", settings.host, settings.port, settings.max_webhook_path)


async def on_cleanup(app: web.Application) -> None:
    from max_bot.core.api_client import core_api

    await core_api.close()
    await app["bot"].session.close()
    storage = app["dispatcher"].storage
    close = getattr(storage, "close", None)
    if close:
        await close()


def create_app() -> web.Application:
    """Фабрика aiohttp-приложения (используется и uvicorn/gunicorn-совместимо через aiohttp)."""
    setup_logging()
    bot = create_bot()
    dispatcher = create_dispatcher()
    setup_routers(dispatcher)

    app = web.Application()
    app["bot"] = bot
    app["dispatcher"] = dispatcher

    app.router.add_post(settings.max_webhook_path, handle_max_webhook)
    app.router.add_get("/healthz", handle_health)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def main() -> None:
    app = create_app()
    web.run_app(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    asyncio.run(asyncio.sleep(0))  # ensure loop tools import cleanly
    main()
