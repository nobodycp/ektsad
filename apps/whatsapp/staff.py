"""A linked employee uses the same actions as Telegram, delivered on WhatsApp."""

from apps.telegram.webhook import handle_update
from apps.whatsapp.flow import _choice_id
from apps.whatsapp.links import find_link


def linked_employee(phone):
    link = find_link(phone)
    if link is None or not link.user.is_active:
        return None
    if getattr(link.user, "preview_as_citizen", False):
        return None
    return link.user


def handle_staff(phone, message):
    chat = f"wa:{phone}"
    kind = message.get("type")
    if kind in {"interactive", "button"}:
        handle_update({
            "callback_query": {
                "id": "",
                "from": {"id": phone},
                "data": _choice_id(message),
                "message": {"chat": {"id": chat}, "message_id": 1},
            }
        })
        return
    if kind == "text":
        handle_update({
            "message": {
                "chat": {"id": chat},
                "from": {"id": phone},
                "text": ((message.get("text") or {}).get("body") or "").strip(),
            }
        })
        return
    if kind == "location":
        handle_update({
            "message": {
                "chat": {"id": chat},
                "from": {"id": phone},
                "location": message.get("location") or {},
            }
        })
        return
    from apps.whatsapp.client import send_text
    send_text(phone, "أرسل نصاً أو اختر من القائمة.")
