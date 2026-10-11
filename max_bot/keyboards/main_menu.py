"""Главное меню бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆕 Создать заявку", callback_data="ticket_create"),
                InlineKeyboardButton(text="📋 Мои заявки", callback_data="ticket_list"),
            ],
            [
                InlineKeyboardButton(text="👤 Профиль и баланс", callback_data="profile"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
            ],
        ]
    )
