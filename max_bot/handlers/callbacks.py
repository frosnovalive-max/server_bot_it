"""Обработка нажатий inline_keyboard, не покрытых специализированными роутерами.

Сюда попадают «неизвестные» callback_data — отвечаем подсказкой и возвращаем
в главное меню, чтобы диалог не зависал.
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from max_bot.keyboards.main_menu import build_main_menu
from max_bot.utils.helpers import safe_answer_callback

logger = logging.getLogger(__name__)

router = Router(name="callbacks")


@router.callback_query()
async def unknown_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Fallback для всех непрямых кнопок (регистрируется последним!)."""
    logger.info("Unhandled callback: %r", callback.data)
    await safe_answer_callback(callback)
    await state.clear()
    await callback.message.edit_text(
        "🤔 Не понял кнопку. Выберите действие:", reply_markup=build_main_menu()
    )
