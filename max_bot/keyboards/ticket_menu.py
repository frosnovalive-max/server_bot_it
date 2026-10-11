"""Клавиатуры для работы с тикетами (создание, список, детали)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_type_keyboard(types: list[dict]) -> InlineKeyboardMarkup:
    """Кнопки с типами обращений из GET /api/v1/references/ticket-types."""
    rows = []
    row: list[InlineKeyboardButton] = []
    for t in types:
        row.append(
            InlineKeyboardButton(
                text=t.get("name", f"Тип #{t['id']}"),
                callback_data=f"type_{t['id']}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_address_keyboard(addresses: list[dict]) -> InlineKeyboardMarkup:
    """Кнопки с адресами корпусов из GET /api/v1/references/addresses."""
    rows = []
    for a in addresses:
        rows.append(
            [
                InlineKeyboardButton(
                    text=a.get("title", a.get("address", str(a["id"]))),
                    callback_data=f"addr_{a['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_skip_keyboard(next_label: str, skip_callback: str) -> InlineKeyboardMarkup:
    """Одна кнопка действия + пропуск шага."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=skip_callback)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def build_tickets_list_keyboard(tickets: list[dict]) -> InlineKeyboardMarkup:
    """Список кнопок «открыть тикет №N» + возврат в меню."""
    rows = []
    for ticket in tickets[:10]:  # не больше 10 кнопок
        number = ticket.get("ticket_number") or ticket.get("number") or ticket["id"]
        status = ticket.get("status_display") or ticket.get("status", "")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"№{number} — {ticket.get('title', '')[:35]} [{status}]",
                    callback_data=f"ticket_{ticket['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_ticket_actions_keyboard(ticket: dict) -> InlineKeyboardMarkup:
    """Действия над тикетом: добавить сообщение, закрыть/отменить (по статусу)."""
    tid = ticket["id"]
    status = (ticket.get("status") or "").lower()
    rows = [
        [
            InlineKeyboardButton(
                text="💬 Добавить сообщение", callback_data=f"ticket_add_message_{tid}"
            )
        ]
    ]
    if status in ("new", "open", "in_progress", "active"):
        rows.append(
            [
                InlineKeyboardButton(text="✅ Закрыть", callback_data=f"ticket_close_{tid}"),
                InlineKeyboardButton(text="🗑 Отменить", callback_data=f"ticket_cancel_{tid}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ К списку", callback_data="ticket_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
