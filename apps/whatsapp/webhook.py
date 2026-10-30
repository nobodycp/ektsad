import os

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def _verify_token():
    return getattr(settings, "WHATSAPP_VERIFY_TOKEN", "") or os.environ.get("WHATSAPP_VERIFY_TOKEN", "")


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
    return HttpResponse("ok", content_type="text/plain")
