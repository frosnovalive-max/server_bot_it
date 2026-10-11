"""Создание, просмотр и управление тикетами.

Многошаговый диалог создания заявки (FSM, состояния в Redis):
  waiting_for_type -> waiting_for_address -> waiting_for_cabinet
  -> waiting_for_title -> waiting_for_description -> waiting_for_confirmation

Вся бизнес-логика (списание баллов, лимиты) — на стороне Core API;
бот только передает данные и показывает результат.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from max_bot.core.api_client import core_api
from max_bot.keyboards.confirmation import build_confirmation_keyboard
from max_bot.keyboards.main_menu import build_main_menu
from max_bot.keyboards.ticket_menu import (
    build_address_keyboard,
    build_skip_keyboard,
    build_ticket_actions_keyboard,
    build_tickets_list_keyboard,
    build_type_keyboard,
)
from max_bot.services.message_formatter import (
    format_confirmation_summary,
    format_insufficient_points,
    format_ticket_created,
    format_ticket_details,
    format_tickets_list,
)
from max_bot.states.ticket_states import TicketStates
from max_bot.utils.helpers import safe_answer_callback, truncate

logger = logging.getLogger(__name__)

router = Router(name="tickets")


# ---------------------------------------------------------------------------
# Вход в сценарий создания заявки
# ---------------------------------------------------------------------------
async def _start_creation(callback, message, state: FSMContext) -> None:
    """Показывает выбор типа обращения (GET /api/v1/references/ticket-types)."""
    await state.set_state(TicketStates.waiting_for_type)
    types = await core_api.get_ticket_types()
    keyboard = build_type_keyboard(types)
    if callback is not None:
        await callback.message.edit_text("Выберите тип обращения:", reply_markup=keyboard)
    elif message is not None:
        await message.answer("Выберите тип обращения:", reply_markup=keyboard)


@router.callback_query(F.data == "ticket_create")
async def cb_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    await _start_creation(callback=callback, message=None, state=state)


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext) -> None:
    await _start_creation(callback=None, message=message, state=state)


# ---------------------------------------------------------------------------
# Шаг 1. Тип обращения
# ---------------------------------------------------------------------------
@router.callback_query(TicketStates.waiting_for_type, F.data.startswith("type_"))
async def process_type(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    type_id = callback.data.split("_", 1)[1]
    await state.update_data(type_id=type_id)
    await state.set_state(TicketStates.waiting_for_address)

    addresses = await core_api.get_addresses()
    keyboard = build_address_keyboard(addresses)
    await callback.message.edit_text("Выберите адрес (корпус):", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Шаг 2. Адрес
# ---------------------------------------------------------------------------
@router.callback_query(TicketStates.waiting_for_address, F.data.startswith("addr_"))
async def process_address(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    address_id = callback.data.split("_", 1)[1]
    await state.update_data(address_id=address_id)
    await state.set_state(TicketStates.waiting_for_cabinet)

    await callback.message.edit_text(
        "Введите номер кабинета (или нажмите «Пропустить»):",
        reply_markup=build_skip_keyboard("Пропустить", "cabinet_skip"),
    )


# ---------------------------------------------------------------------------
# Шаг 3. Кабинет (опционально)
# ---------------------------------------------------------------------------
@router.callback_query(TicketStates.waiting_for_cabinet, F.data == "cabinet_skip")
async def skip_cabinet(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    await state.update_data(cabinet=None)
    await state.set_state(TicketStates.waiting_for_title)
    await callback.message.edit_text("Введите тему заявки (кратко, до 100 символов):")


@router.message(TicketStates.waiting_for_cabinet, F.text)
async def process_cabinet(message: Message, state: FSMContext) -> None:
    await state.update_data(cabinet=truncate(message.text, 32))
    await state.set_state(TicketStates.waiting_for_title)
    await message.answer("Введите тему заявки (кратко, до 100 символов):")


# ---------------------------------------------------------------------------
# Шаг 4. Тема
# ---------------------------------------------------------------------------
@router.message(TicketStates.waiting_for_title, F.text)
async def process_title(message: Message, state: FSMContext) -> None:
    title = truncate(message.text, 100)
    await state.update_data(title=title)
    await state.set_state(TicketStates.waiting_for_description)
    await message.answer(
        "Опишите проблему подробно\n"
        "(что сломалось, когда началось, что уже пробовали):"
    )


# ---------------------------------------------------------------------------
# Шаг 5. Описание -> подтверждение
# ---------------------------------------------------------------------------
@router.message(TicketStates.waiting_for_description, F.text)
async def process_description(message: Message, state: FSMContext) -> None:
    description = truncate(message.text, 2000)
    await state.update_data(description=description)
    await state.set_state(TicketStates.waiting_for_confirmation)

    data = await state.get_data()
    names = await _resolve_names(data)
    await message.answer(
        format_confirmation_summary(data, names),
        reply_markup=build_confirmation_keyboard(),
    )


async def _resolve_names(data: dict) -> dict:
    """Подтягиваем человекочитаемые названия типа/адреса из справочников."""
    names = {"type": "—", "address": "—"}
    try:
        for t in await core_api.get_ticket_types():
            if str(t["id"]) == str(data.get("type_id")):
                names["type"] = t.get("name", str(t["id"]))
        for a in await core_api.get_addresses():
            if str(a["id"]) == str(data.get("address_id")):
                names["address"] = a.get("title") or a.get("address", str(a["id"]))
    except Exception as exc:  # справочники не критичны для подтверждения
        logger.warning("Cannot resolve reference names: %s", exc)
    return names


# ---------------------------------------------------------------------------
# Шаг 6. Подтверждение / редактирование описания
# ---------------------------------------------------------------------------
@router.callback_query(TicketStates.waiting_for_confirmation, F.data == "confirm_yes")
async def confirm_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    data = await state.get_data()

    response = await core_api.create_ticket(
        author_max_user_id=callback.from_user.id,
        type_id=data["type_id"],
        address_id=data["address_id"],
        cabinet=data.get("cabinet"),
        title=data["title"],
        description=data["description"],
    )

    if response.get("status") == "created":
        text = format_ticket_created(response)
    elif response.get("status") == "insufficient_points":
        text = format_insufficient_points(response)
    else:
        text = f"Ответ Core API: {response}"

    await state.clear()
    await callback.message.edit_text(text, reply_markup=build_main_menu())


@router.callback_query(TicketStates.waiting_for_confirmation, F.data == "confirm_edit_desc")
async def edit_description(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    await state.set_state(TicketStates.waiting_for_description)
    await callback.message.edit_text("Введите новое описание заявки:")


@router.callback_query(F.data == "cancel")
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена любого многошагового сценария."""
    await safe_answer_callback(callback)
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено.", reply_markup=build_main_menu()
    )


# ---------------------------------------------------------------------------
# Список тикетов
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "ticket_list")
async def show_tickets(callback: CallbackQuery) -> None:
    await safe_answer_callback(callback)
    tickets = await core_api.get_user_tickets(
        max_user_id=callback.from_user.id, status="active"
    )
    text = format_tickets_list(tickets, status_filter="active")
    keyboard = build_tickets_list_keyboard(tickets)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.message(Command("tickets"))
async def cmd_tickets(message: Message) -> None:
    tickets = await core_api.get_user_tickets(
        max_user_id=message.from_user.id, status="active"
    )
    await message.answer(
        format_tickets_list(tickets), reply_markup=build_tickets_list_keyboard(tickets)
    )


# ---------------------------------------------------------------------------
# Детали тикета
# ---------------------------------------------------------------------------
@router.callback_query(F.data.regexp(r"^ticket_\d+$"))
async def show_ticket_details(callback: CallbackQuery) -> None:
    await safe_answer_callback(callback)
    ticket_id = callback.data.split("_", 1)[1]
    ticket = await core_api.get_ticket(ticket_id)
    text = format_ticket_details(ticket)
    keyboard = build_ticket_actions_keyboard(ticket)
    await callback.message.edit_text(text, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Добавление сообщения в тикет
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("ticket_add_message_"))
async def start_adding_message(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_answer_callback(callback)
    ticket_id = callback.data.rsplit("_", 1)[1]
    await state.set_state(TicketStates.waiting_for_message)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer("Введите сообщение для заявки:")


@router.message(TicketStates.waiting_for_message, F.text)
async def process_ticket_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ticket_id = data["ticket_id"]

    await core_api.add_ticket_message(
        ticket_id=ticket_id,
        author_max_user_id=message.from_user.id,
        text=truncate(message.text, 2000),
    )
    await message.answer("✅ Сообщение добавлено")
    await state.clear()


# ---------------------------------------------------------------------------
# Закрытие / отмена тикета
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("ticket_close_"))
async def close_ticket(callback: CallbackQuery) -> None:
    await safe_answer_callback(callback)
    ticket_id = callback.data.rsplit("_", 1)[1]
    ticket = await core_api.close_ticket(ticket_id, callback.from_user.id)
    await callback.message.edit_text(
        format_ticket_details(ticket),
        reply_markup=build_ticket_actions_keyboard(ticket),
    )


@router.callback_query(F.data.startswith("ticket_cancel_"))
async def cancel_ticket(callback: CallbackQuery) -> None:
    await safe_answer_callback(callback)
    ticket_id = callback.data.rsplit("_", 1)[1]
    await core_api.cancel_ticket(ticket_id, callback.from_user.id)
    await callback.message.edit_text(
        f"🗑 Заявка #{ticket_id} отменена.",
        reply_markup=build_main_menu(),
    )
