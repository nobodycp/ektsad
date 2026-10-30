import os

import httpx
from django.conf import settings

GRAPH = "https://graph.facebook.com/v22.0"


def _token():
    return getattr(settings, "WHATSAPP_TOKEN", "") or os.environ.get("WHATSAPP_TOKEN", "")


def _phone_id():
    return getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def _headers():
    return {"Authorization": f"Bearer {_token()}"}


def send(phone, payload):
    token, phone_id = _token(), _phone_id()
    if not token or not phone_id:
        return False
    body = {"messaging_product": "whatsapp", "to": phone, **payload}
    response = httpx.post(f"{GRAPH}/{phone_id}/messages", headers=_headers(), json=body, timeout=20)
    response.raise_for_status()
    return True


def send_text(phone, body):
    return send(phone, {"type": "text", "text": {"body": body}})


def send_buttons(phone, body, buttons):
    return send(phone, {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": item["id"], "title": item["title"][:20]}}
                    for item in buttons[:3]
                ],
            },
        },
    })


def send_list(phone, body, rows, button="اختر"):
    if not rows:
        return send_text(phone, body)
    return send(phone, {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button[:20],
                "sections": [{
                    "title": "الخيارات",
                    "rows": [{"id": item["id"], "title": item["title"][:24]} for item in rows[:10]],
                }],
            },
        },
    })


def send_location_request(phone, body):
    return send(phone, {
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {"text": body},
            "action": {"name": "send_location"},
        },
    })


def send_image_bytes(phone, content, filename, caption=""):
    token, phone_id = _token(), _phone_id()
    if not token or not phone_id:
        return False
    uploaded = httpx.post(
        f"{GRAPH}/{phone_id}/media",
        headers=_headers(),
        data={"messaging_product": "whatsapp", "type": "image/jpeg"},
        files={"file": (filename, content, "image/jpeg")},
        timeout=30,
    )
    uploaded.raise_for_status()
    media_id = uploaded.json().get("id")
    if not media_id:
        return False
    image = {"id": media_id}
    if caption:
        image["caption"] = caption
    return send(phone, {"type": "image", "image": image})


def download_media(media_id):
    meta = httpx.get(f"{GRAPH}/{media_id}", headers=_headers(), timeout=20)
    meta.raise_for_status()
    info = meta.json()
    content = httpx.get(info["url"], headers=_headers(), timeout=30)
    content.raise_for_status()
    mime = info.get("mime_type") or "image/jpeg"
    ext = {"image/png": "png", "image/webp": "webp"}.get(mime, "jpg")
    return content.content, f"whatsapp.{ext}"
