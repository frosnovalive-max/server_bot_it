"""Настройки приложения, загружаемые из переменных окружения (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все конфигурационные параметры бота."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- MAX Bot API ---
    max_bot_token: str = ""
    """Токен бота, выданный в панели разработчика MAX."""

    max_api_url: str = "https://maxapi.ru/v3"
    """Базовый URL REST-API мессенджера MAX (dev.max.ru/docs)."""

    max_webhook_path: str = "/webhook/max"
    """Путь, по которому MAX будет слать вебхуки (message_new и т.д.)."""

    webhook_url: str = ""
    """Публичный HTTPS URL для регистрации вебхука, напр. https://bot.example.com/webhook/max"""

    # --- Core API (бизнес-логика) ---
    core_api_url: str = "http://core-api:8000"
    """Базовый URL Core API колледжа."""

    core_api_key: str = ""
    """API-ключ для авторизации запросов к Core API (заголовок X-API-Key)."""

    core_api_timeout: float = 15.0
    """Таймаут HTTP-запросов к Core API, сек."""

    # --- Redis (FSM) ---
    redis_url: str = "redis://localhost:6379/0"
    """Строка подключения к Redis, используется RedisStorage."""

    # --- Webhook-сервер ---
    host: str = "0.0.0.0"
    port: int = 8080

    # --- Прочее ---
    environment: str = "production"
    log_level: str = "INFO"

    secret_token: str = ""
    """Секрет, который MAX передает в заголовке X-Max-Webhook-Secret (проверка подлинности вебхука)."""


@lru_cache
def get_settings() -> Settings:
    """Возвращает singleton настроек (кэшируется)."""
    return Settings()
