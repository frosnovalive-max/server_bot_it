"""Клавиатуры подтверждения (да/нет) и отмены шага."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение создания заявки: да/нет."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_yes"),
                InlineKeyboardButton(text="✏️ Изменить описание", callback_data="confirm_edit_desc"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )
