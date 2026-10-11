"""Вспомогательные функции."""

import logging

from aiogram.fsm.context import FSMContext

from max_bot.core.api_client import core_api

logger = logging.getLogger(__name__)


async def sync_user_with_core(bot, user_id: int) -> dict | None:
    """Синхронизирует профиль пользователя MAX с Core API.

    1. GET /v3/users/{user_id}   — получаем профиль из MAX;
    2. PUT /api/v1/users/{id}/profile — создаем/обновляем в Core API.

    Возвращает профиль из MAX (или None при ошибке). Ошибки не должны
    блокировать диалог — логируем и идем дальше.
    """
    try:
        max_profile = await bot.get_max_user(user_id)
        await core_api.upsert_user(
            max_user_id=user_id,
            first_name=max_profile.get("first_name"),
            name=max_profile.get("name") or max_profile.get("last_name"),
            username=max_profile.get("username") or max_profile.get("nickname"),
            raw_profile=max_profile,
        )
        logger.info("User %s synced with Core API", user_id)
        return max_profile
    except Exception as exc:
        logger.warning("Profile sync failed for user %s: %s", user_id, exc)
        return None


async def safe_answer_callback(callback, **kwargs) -> None:
    """Answer callback без падения, если метод недоступен в MAX."""
    try:
        await callback.answer(**kwargs)
    except Exception:
        pass


async def reset_state(state: FSMContext) -> None:
    await state.clear()


def truncate(text: str, length: int = 64) -> str:
    text = text.strip()
    return text if len(text) <= length else text[: length - 1] + "…"
