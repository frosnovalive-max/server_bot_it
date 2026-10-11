"""Генерация inline-клавиатур для MAX (callback_data)."""

from max_bot.keyboards.confirmation import build_confirmation_keyboard, build_cancel_keyboard
from max_bot.keyboards.main_menu import build_main_menu
from max_bot.keyboards.ticket_menu import (
    build_address_keyboard,
    build_ticket_actions_keyboard,
    build_tickets_list_keyboard,
    build_type_keyboard,
)

__all__ = [
    "build_main_menu",
    "build_type_keyboard",
    "build_address_keyboard",
    "build_tickets_list_keyboard",
    "build_ticket_actions_keyboard",
    "build_confirmation_keyboard",
    "build_cancel_keyboard",
]
