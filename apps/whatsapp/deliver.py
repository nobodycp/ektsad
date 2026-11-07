"""Turn a Telegram inline keyboard into WhatsApp buttons or a list."""

from apps.whatsapp.client import send_buttons, send_image_bytes, send_list, send_text


def _buttons(markup):
    rows = (markup or {}).get("inline_keyboard") or []
    found = []
    for row in rows:
        for button in row:
            data = str(button.get("callback_data") or "")
            title = str(button.get("text") or "").strip()
            if data and title:
                found.append({"id": data[:200], "title": title})
    return found


def deliver(phone, text="", photo="", markup=None):
    body = (text or "").strip() or "اختر."
    if photo:
        from django.core.files.storage import default_storage
        if default_storage.exists(photo):
            with default_storage.open(photo, "rb") as handle:
                send_image_bytes(phone, handle.read(), "photo.jpg", body[:1000])
            body = "اختر."
    buttons = _buttons(markup)
    if not buttons:
        if not photo:
            send_text(phone, body[:4000])
        return
    if len(buttons) <= 3:
        send_buttons(phone, body[:1000], buttons)
        return
    for index in range(0, len(buttons), 10):
        send_list(phone, body[:1000] if index == 0 else "تابع الخيارات.", buttons[index:index + 10])
