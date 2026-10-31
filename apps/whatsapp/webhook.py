import hashlib
import hmac
import json
import os

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.whatsapp.client import GraphError, send_text
from apps.whatsapp.flow import handle_message
from apps.whatsapp.models import WhatsAppInbound


def _verify_token():
    return getattr(settings, "WHATSAPP_VERIFY_TOKEN", "") or os.environ.get("WHATSAPP_VERIFY_TOKEN", "")


def _signature_ok(request):
    secret = getattr(settings, "WHATSAPP_APP_SECRET", "") or os.environ.get("WHATSAPP_APP_SECRET", "")
    if not secret:
        return True
    header = request.headers.get("X-Hub-Signature-256", "")
    digest = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header, f"sha256={digest}")


def _message_key(message_id):
    message_id = str(message_id)
    if len(message_id) <= 500:
        return message_id
    return hashlib.sha256(message_id.encode()).hexdigest()


def _messages(payload):
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            for message in value.get("messages") or []:
                sender = message.get("from")
                if not sender and value.get("contacts"):
                    sender = (value["contacts"][0] or {}).get("wa_id")
                if message.get("id") and sender:
                    message = dict(message)
                    message["from"] = sender
                    yield message


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    if request.method == "GET":
        token = _verify_token()
        mode = request.GET.get("hub.mode", "")
        given = request.GET.get("hub.verify_token", "")
        challenge = request.GET.get("hub.challenge", "")
        if not token or mode != "subscribe" or given != token or not challenge:
            return HttpResponseForbidden("forbidden")
        return HttpResponse(challenge, content_type="text/plain")
    if not _signature_ok(request):
        return HttpResponseForbidden("forbidden")
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponse("ok", content_type="text/plain")
    for message in _messages(payload):
        key = _message_key(message["id"])
        _created = WhatsAppInbound.objects.get_or_create(message_id=key)[1]
        if not _created:
            continue
        try:
            handle_message(message["from"], message)
        except GraphError as exc:
            send_text(message["from"], f"تعذر إكمال الخطوة.\n{exc}")
        except Exception:
            WhatsAppInbound.objects.filter(message_id=key).delete()
            raise
    return HttpResponse("ok", content_type="text/plain")
