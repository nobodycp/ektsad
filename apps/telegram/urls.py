import json

from django.http import JsonResponse
from django.urls import path
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.telegram.links import NOT_CONFIGURED, create_staff_link
from apps.telegram.models import TelegramLink, TelegramOutbox, TelegramWebhookStatus
from apps.telegram.webhook import _value, _status_update, handle_update, record_update


def _admin(request):
    return request.user.is_authenticated and request.user.role == User.Role.ADMIN


@csrf_exempt
@require_http_methods(["POST"])
def webhook(request):
    if not _value("TELEGRAM_WEBHOOK_SECRET") or request.headers.get("X-Telegram-Bot-Api-Secret-Token") != _value("TELEGRAM_WEBHOOK_SECRET"):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        update = json.loads(request.body or "{}")
        update_id = update["update_id"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"detail": "بيانات غير صالحة."}, status=400)
    if not record_update(update_id):
        return JsonResponse({"ok": True})
    _status_update(last_update_at=timezone.now())
    try:
        handle_update(update)
    except Exception:
        from apps.telegram.models import TelegramUpdate
        TelegramUpdate.objects.filter(update_id=update_id).delete()
        raise
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def health(request):
    if not _admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    status = TelegramWebhookStatus.current()
    pending = TelegramOutbox.objects.filter(status=TelegramOutbox.Status.PENDING)
    oldest = pending.order_by("created_at").values_list("created_at", flat=True).first()
    return JsonResponse({
        "registered": status.registered,
        "last_error": status.last_error,
        "last_update_at": status.last_update_at.isoformat() if status.last_update_at else None,
        "pending_count": pending.count(),
        "oldest_wait": oldest.isoformat() if oldest else None,
    })


@require_http_methods(["POST", "DELETE"])
def user_telegram_link(request, pk):
    if not _admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    user = User.objects.filter(pk=pk).first()
    if user is None:
        return JsonResponse({"detail": "غير موجود."}, status=404)
    if request.method == "DELETE":
        TelegramLink.objects.filter(user=user).delete()
        return JsonResponse({}, status=204)
    try:
        link = create_staff_link(user)
    except ValueError:
        return JsonResponse({"detail": NOT_CONFIGURED}, status=400)
    return JsonResponse({"link": link})


urlpatterns = [
    path("telegram/webhook/", webhook),
    path("telegram/health/", health),
    path("users/<int:pk>/telegram-link/", user_telegram_link),
]
