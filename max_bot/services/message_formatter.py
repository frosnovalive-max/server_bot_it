"""Шаблоны и форматирование текстов сообщений бота."""

STATUS_EMOJI = {
    "new": "🆕",
    "open": "🆕",
    "in_progress": "⚙️",
    "active": "⚙️",
    "resolved": "✅",
    "closed": "🔒",
    "cancelled": "🗑",
    "rejected": "❌",
}


def _status_line(ticket: dict) -> str:
    status = (ticket.get("status") or "").lower()
    emoji = STATUS_EMOJI.get(status, "ℹ️")
    display = ticket.get("status_display") or status
    return f"{emoji} Статус: {display}"


def format_welcome(first_name: str) -> str:
    return (
        f"👋 Привет, {first_name}!\n\n"
        "Я — бот IT-службы колледжа. Здесь можно:\n"
        "• создать заявку в техподдержку;\n"
        "• посмотреть статус своих заявок;\n"
        "• увидеть профиль, баланс баллов и рейтинг.\n\n"
        "Выберите действие:"
    )


def format_help() -> str:
    return (
        "ℹ️ <b>Команды бота</b>\n\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/new — создать заявку\n"
        "/tickets — мои заявки\n"
        "/profile — профиль и баланс\n\n"
        "<b>Как создать заявку:</b>\n"
        "1. Нажмите «🆕 Создать заявку»\n"
        "2. Выберите тип обращения и адрес\n"
        "3. Укажите кабинет (необязательно), тему и описание\n"
        "4. Подтвердите — заявка уйдет мастеру\n\n"
        "За создание заявки списываются баллы according to тарифам Core API."
    )


def format_ticket_created(response: dict) -> str:
    number = response.get("ticket_number")
    balance = response.get("new_balance")
    text = f"✅ Заявка №{number} создана!\n"
    if balance is not None:
        text += f"💰 Баланс баллов: {balance}"
    return text


def format_insufficient_points(response: dict) -> str:
    balance = response.get("current_balance", 0)
    return (
        "❌ Недостаточно баллов для создания заявки.\n"
        f"Текущий баланс: {balance}\n\n"
        "Пополнить баланс можно через старосту или администрацию."
    )


def format_tickets_list(tickets: list[dict], status_filter: str = "active") -> str:
    title = {"active": "активные", "all": "все", "closed": "закрытые"}.get(
        status_filter, status_filter
    )
    if not tickets:
        return f"📋 У вас нет {title} заявок."
    lines = [f"📋 Ваши {title} заявки ({len(tickets)}):\n"]
    for t in tickets[:10]:
        number = t.get("ticket_number") or t.get("number") or t["id"]
        emoji = STATUS_EMOJI.get((t.get("status") or "").lower(), "ℹ️")
        lines.append(f"{emoji} №{number} — {t.get('title', 'Без темы')}")
    if len(tickets) > 10:
        lines.append(f"\n…и ещё {len(tickets) - 10}. Нажмите кнопку нужной заявки ниже.")
    else:
        lines.append("\nНажмите кнопку нужной заявки ниже.")
    return "\n".join(lines)


def format_ticket_details(ticket: dict) -> str:
    number = ticket.get("ticket_number") or ticket.get("number") or ticket["id"]
    parts = [
        f"🎫 <b>Заявка №{number}</b>",
        f"📌 Тема: {ticket.get('title', '—')}",
        _status_line(ticket),
        f"🏷 Тип: {ticket.get('type_name') or ticket.get('type_id', '—')}",
        f"📍 Адрес: {ticket.get('address_title') or ticket.get('address_id', '—')}"
        + (f", каб. {ticket['cabinet']}" if ticket.get("cabinet") else ""),
        f"📝 Описание: {ticket.get('description', '—')}",
    ]
    if ticket.get("created_at"):
        parts.append(f"🗓 Создана: {ticket['created_at']}")
    if ticket.get("assignee_name"):
        parts.append(f"👨‍🔧 Исполнитель: {ticket['assignee_name']}")
    return "\n".join(parts)


def format_profile(profile: dict) -> str:
    return (
        f"👤 {profile.get('first_name', '')} {profile.get('name', '')}\n"
        f"📍 Адрес по умолчанию: {profile.get('default_address', 'не задан')}\n"
        f"⭐ Рейтинг: {profile.get('rating', 0)}\n"
        f"💰 Баланс баллов: {profile.get('points_balance', 0)}"
    )


def format_confirmation_summary(data: dict, names: dict) -> str:
    """Предпросмотр заявки перед подтверждением."""
    return (
        "🧾 Проверьте данные заявки:\n\n"
        f"Тип: {names.get('type', '—')}\n"
        f"Адрес: {names.get('address', '—')}\n"
        f"Кабинет: {data.get('cabinet') or '—'}\n"
        f"Тема: {data.get('title', '—')}\n"
        f"Описание: {data.get('description', '—')}\n\n"
        "Подтверждаете создание?"
    )
