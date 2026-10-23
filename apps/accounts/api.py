import json

from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User


INVALID_CREDENTIALS = "بيانات الدخول غير صحيحة."


@require_http_methods(["POST"])
def login_view(request):
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": INVALID_CREDENTIALS}, status=400)
    login(request, user)
    return JsonResponse({"id": user.pk, "username": user.username})


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
