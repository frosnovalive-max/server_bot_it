"""Подключение к Redis для хранения состояний FSM (aiogram RedisStorage)."""

from redis.asyncio import Redis

from max_bot.core.config import get_settings


def get_redis() -> Redis:
    """Возвращает асинхронный клиент Redis, построенный из REDIS_URL."""
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)
