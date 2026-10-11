"""Регистрация всех роутеров обработчиков.

Порядок подключения важен: tickets/profile/start раньше, чем fallback
callbacks (ловушка для неизвестных кнопок).
"""

from aiogram import Dispatcher

from max_bot.handlers import callbacks, errors, profile, start, tickets


def setup_routers(dp: Dispatcher) -> None:
    dp.include_router(start.router)      # /start, /help, menu, help
    dp.include_router(tickets.router)    # создание/просмотр тикетов (FSM)
    dp.include_router(profile.router)    # профиль, баланс, рейтинг
    dp.include_router(callbacks.router)  # fallback для неизвестных кнопок — ПОСЛЕДНИМ


__all__ = ["setup_routers"]
