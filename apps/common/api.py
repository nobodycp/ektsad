import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.common.models import SystemSettings


def _admin(request):
    from apps.accounts.permissions import allows
    return allows(request.user, "can_manage_settings")


def _public_payload(row):
    return {"web_complaints_enabled": row.web_complaints_enabled}


def _admin_payload(row):
    return {
        **_public_payload(row),
        "telegram_bot_username": row.telegram_bot_username,
        "telegram_bot_configured": bool(row.telegram_bot_token),
        "telegram_webhook_secret_configured": bool(row.telegram_webhook_secret),
    }


@require_http_methods(["GET"])
def public_settings(request):
    return JsonResponse(_public_payload(SystemSettings.current()))


@require_http_methods(["GET", "PATCH"])
def system_settings(request):
    if not _admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    row = SystemSettings.current()
    if request.method == "GET":
        return JsonResponse(_admin_payload(row))
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "بيانات غير صالحة."}, status=400)
    if "web_complaints_enabled" in payload:
        row.web_complaints_enabled = bool(payload["web_complaints_enabled"])
    if "telegram_bot_username" in payload:
        row.telegram_bot_username = str(payload.get("telegram_bot_username") or "").lstrip("@").strip()
    token = str(payload.get("telegram_bot_token") or "").strip()
    secret = str(payload.get("telegram_webhook_secret") or "").strip()
    if token:
        row.telegram_bot_token = token
    if secret:
        row.telegram_webhook_secret = secret
    row.save()
    from apps.telegram.webhook import register_webhook

    register_webhook()
    return JsonResponse(_admin_payload(row))
