"""Адаптер формата MAX Bot API в формат Update aiogram.

MAX (dev.max.ru) доставляет на вебхук события вида:

    message_new / message_callback / user_joined ...

с JSON-телом, отличным от Telegram. Чтобы переиспользовать machinery
aiogram (FSM, middlewares, фильтры F.data), мы конвертируем событие MAX
в словарик, совместимый с pydantic-моделью ``aiogram.types.Update``.

Маппинг полей MAX -> Telegram-подобный формат выполняется функциями ниже.
Если ваш стенд отдает другой формат — правьте только этот файл.
"""

from typing import Any


def _first_name(payload_user: dict) -> str:
    return (
        payload_user.get("first_name")
        or payload_user.get("name")
        or payload_user.get("display_name")
        or "Пользователь"
    )


def map_message_new(payload: dict) -> dict | None:
    """message_new -> {"message": {...}} в стиле Telegram."""
    body = payload.get("body") or {}
    message = body.get("message") or body
    user = message.get("sender") or message.get("from") or body.get("user") or {}
    text = message.get("text") or message.get("body") or ""
    chat_id = message.get("chat_id") or user.get("user_id")
    if chat_id is None:
        return None
    tg_update = {
        "update_id": int(message.get("message_id", 0) or 0),
        "message": {
            "message_id": int(message.get("message_id", 0) or 0),
            "date": int(message.get("timestamp", 0) or 0) or 1,
            "chat": {"id": int(chat_id), "type": "private"},
            "from": {
                "id": int(user.get("user_id", chat_id) or chat_id),
                "is_bot": False,
                "first_name": _first_name(user),
                "username": user.get("username"),
            },
            "text": text,
        },
    }
    # aiogram ожидает text именно строкой
    tg_update["message"]["text"] = text
    return tg_update


def map_message_callback(payload: dict) -> dict | None:
    """message_callback -> {"callback_query": {...}} в стиле Telegram."""
    body = payload.get("body") or {}
    callback = body.get("callback") or body
    user = callback.get("user") or {}
    message = callback.get("message") or body.get("message") or {}
    chat_id = message.get("chat_id") or user.get("user_id")
    if chat_id is None:
        return None
    return {
        "update_id": int(callback.get("sequence_id", 0) or 0),
        "callback_query": {
            "id": str(callback.get("callback_id") or callback.get("id") or "0"),
            "data": str(callback.get("payload") or callback.get("data") or ""),
            "from": {
                "id": int(user.get("user_id", 0) or 0),
                "is_bot": False,
                "first_name": _first_name(user),
                "username": user.get("username"),
            },
            "chat_instance": "max",
            "message": {
                "message_id": int(message.get("message_id", 0) or 0),
                "date": int(message.get("timestamp", 0) or 0) or 1,
                "chat": {"id": int(chat_id), "type": "private"},
                "from": {
                    "id": int(message.get("sender", {}).get("user_id", 0) or 0),
                    "is_bot": True,
                    "first_name": "IT-служба",
                },
                "text": message.get("text") or "",
            },
        },
    }


def map_user_joined(payload: dict) -> dict | None:
    """user_joined -> синтетическое сообщение "/start"."""
    body = payload.get("body") or {}
    user = body.get("user") or {}
    user_id = user.get("user_id")
    if user_id is None:
        return None
    return {
        "update_id": 0,
        "message": {
            "message_id": 0,
            "date": 1,
            "chat": {"id": int(user_id), "type": "private"},
            "from": {
                "id": int(user_id),
                "is_bot": False,
                "first_name": _first_name(user),
                "username": user.get("username"),
            },
            "text": "/start",
        },
    }


MAX_EVENT_MAP: dict[str, Any] = {
    "message_new": map_message_new,
    "message_created": map_message_new,
    "message_callback": map_message_callback,
    "callback_received": map_message_callback,
    "user_joined": map_user_joined,
    "bot_started": map_user_joined,
}


def convert_max_update(payload: dict) -> dict | None:
    """Конвертирует raw payload вебхука MAX в Telegram-совместимый update."""
    event_type = payload.get("update_type") or payload.get("event") or ""
    if not event_type:
        # автоопределение по структуре
        body = payload.get("body") or {}
        if "callback" in body:
            event_type = "message_callback"
        elif "message" in body:
            event_type = "message_new"
        elif "user" in body:
            event_type = "user_joined"

    mapper = MAX_EVENT_MAP.get(event_type)
    if mapper is None:
        return None
    return mapper(payload)
