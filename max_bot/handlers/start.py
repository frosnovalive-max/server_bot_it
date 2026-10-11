"""Обработчики команд /start, /help и главного меню."""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from max_bot.keyboards.main_menu import build_main_menu
from max_bot.services.message_formatter import format_help, format_welcome
from max_bot.utils.helpers import safe_answer_callback, sync_user_with_core

logger = logging.getLogger(__name__)

router = Router(name="start")


async def _show_menu(message: Message, state: FSMContext) -> None:
    """Сбрасывает FSM и показывает главное меню."""
    await state.clear()
    await message.answer(format_welcome(message.from_user.first_name),
                        reply_markup=build_main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot) -> None:
    """/start — синхронизация профиля с Core API + главное меню.

    При первом взаимодействии бот получает профиль из MAX
    (GET /v3/users/{id}) и отправляет его в Core API
    (PUT /api/v1/users/{max_user_id}/profile).
    """
    await sync_user_with_core(bot, message.from_user.id)
    await _show_menu(message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """/help — справка по командам и сценариям."""
    await message.answer(format_help())


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await safe_answer_callback(callback)
    await callback.message.answer(format_help())


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню из любого экрана."""
    await safe_answer_callback(callback)
    await state.clear()
    await callback.message.edit_text(
        format_welcome(callback.from_user.first_name),
        reply_markup=build_main_menu(),
    )
