import hashlib
import hmac
import json
import os

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

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


def _messages(payload):
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            for message in (change.get("value") or {}).get("messages") or []:
                if message.get("id") and message.get("from"):
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
        _created = WhatsAppInbound.objects.get_or_create(message_id=message["id"])[1]
        if not _created:
            continue
        try:
            handle_message(message["from"], message)
        except Exception:
            WhatsAppInbound.objects.filter(message_id=message["id"]).delete()
            raise
    return HttpResponse("ok", content_type="text/plain")
