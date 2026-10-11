"""Глобальные обработчики ошибок Core API и непредвиденных исключений."""

import logging

from aiogram import Dispatcher
from aiogram.types.error_event import ErrorEvent

from max_bot.core.api_client import CoreApiError

logger = logging.getLogger(__name__)


def register_error_handlers(dp: Dispatcher) -> None:
    dp.errors.register(global_error_handler)


async def global_error_handler(event: ErrorEvent) -> None:
    """Маппит CoreApiError на понятные пользователю сообщения."""
    exception = event.exception

    if isinstance(exception, CoreApiError):
        logger.warning("CoreApiError handled: %s", exception)
        if exception.status_code == 402:
            text = "❌ Недостаточно баллов для выполнения действия"
        elif exception.status_code == 429:
            text = "⏳ Превышен лимит. Попробуйте позже"
        elif exception.status_code == 403:
            text = "🚫 Вы заблокированы. Обратитесь в поддержку"
        elif exception.status_code == 503:
            text = "🛠 Сервис временно недоступен. Попробуйте позже"
        else:
            text = "❌ Произошла ошибка. Попробуйте позже"
    else:
        logger.exception("Unexpected error: %s", exception)
        text = "❌ Произошла непредвиденная ошибка. Уже чиним 🛠"

    update = event.update
    # Отвечаем туда, откуда прилетело событие (message или callback)
    if update is not None:
        try:
            if update.callback_query and update.callback_query.message:
                await update.callback_query.message.answer(text)
            elif update.message:
                await update.message.answer(text)
        except Exception:
            logger.exception("Cannot deliver error message to user")
