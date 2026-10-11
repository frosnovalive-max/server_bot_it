"""Просмотр профиля, баланса и рейтинга (данные из Core API)."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from max_bot.core.api_client import core_api
from max_bot.services.message_formatter import format_profile
from max_bot.utils.helpers import safe_answer_callback, sync_user_with_core

logger = logging.getLogger(__name__)

router = Router(name="profile")


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery, bot) -> None:
    """Кнопка «Профиль и баланс» в главном меню."""
    await safe_answer_callback(callback)
    user_id = callback.from_user.id
    try:
        profile = await core_api.get_user_profile(max_user_id=user_id)
    except Exception:
        # Пользователь мог еще не существовать в Core API — синхронизируем и повторяем
        await sync_user_with_core(bot, user_id)
        profile = await core_api.get_user_profile(max_user_id=user_id)

    await callback.message.edit_text(format_profile(profile))


@router.message(Command("profile"))
async def cmd_profile(message: Message, bot) -> None:
    """/profile — профиль, рейтинг и баланс баллов."""
    user_id = message.from_user.id
    try:
        profile = await core_api.get_user_profile(max_user_id=user_id)
    except Exception:
        await sync_user_with_core(bot, user_id)
        profile = await core_api.get_user_profile(max_user_id=user_id)

    await message.answer(format_profile(profile))
