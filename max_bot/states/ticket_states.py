"""Состояния многошагового диалога создания заявки.

Шаги: выбор типа -> выбор адреса -> кабинет (опц.) -> тема -> описание
-> подтверждение. Отдельная ветка — добавление сообщения в тикет.
"""

from aiogram.fsm.state import State, StatesGroup


class TicketStates(StatesGroup):
    """FSM-состояния процесса создания/ведения тикета."""

    waiting_for_type = State()           # выбор типа обращения
    waiting_for_address = State()        # выбор адреса
    waiting_for_cabinet = State()        # ввод кабинета (можно пропустить)
    waiting_for_title = State()          # ввод темы
    waiting_for_description = State()    # ввод описания
    waiting_for_confirmation = State()   # подтверждение (да/нет)

    waiting_for_message = State()        # добавление сообщения в существующий тикет
