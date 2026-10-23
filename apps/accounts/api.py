import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User


INVALID_CREDENTIALS = "بيانات الدخول غير صحيحة."


@require_http_methods(["POST"])
def _body(request):
    if request.content_type == "application/json":
        return json.loads(request.body or "{}")
    return request.POST


def login_view(request):
    payload = _body(request)
    username = payload.get("username", "")
    password = payload.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": INVALID_CREDENTIALS}, status=400)
    login(request, user)
    return JsonResponse(_me_payload(user))


def _me_payload(user):
    return {
        "id": user.pk,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return JsonResponse({"detail": "ok"})


@ensure_csrf_cookie
@require_http_methods(["GET"])
def me_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse(_me_payload(request.user))


@require_http_methods(["PATCH"])
def user_detail(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.user.pk != pk and request.user.role != User.Role.ADMIN:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    payload = json.loads(request.body or "{}")
    user = User.objects.get(pk=pk)
    if "display_name" in payload:
        user.display_name = payload["display_name"]
        user.save(update_fields=["display_name"])
    return JsonResponse({"id": user.pk, "username": user.username, "display_name": user.display_name})
