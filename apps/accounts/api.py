import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.accounts.services import delete_user_sessions, reset_password, set_user_password
from apps.geography.models import Governorate, Region


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


def _user_payload(user):
    return {
        "id": user.pk,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "governorate": user.governorate_id,
        "region": user.region_id,
        "can_publish_prices": user.can_publish_prices,
        "can_publish_crossings": user.can_publish_crossings,
        "can_view_all_complaints": user.can_view_all_complaints,
        "is_active": user.is_active,
    }


def _forbidden():
    return JsonResponse({"detail": "Forbidden"}, status=403)


def _is_admin(request):
    return request.user.is_authenticated and request.user.role == User.Role.ADMIN


def _validation_error(error):
    messages = error.messages if hasattr(error, "messages") else [str(error)]
    return JsonResponse({"detail": messages[0]}, status=400)


def _apply_user_fields(user, payload, fields):
    for field in fields:
        if field not in payload:
            continue
        value = payload[field]
        if field == "governorate":
            user.governorate = (
                Governorate.objects.get(pk=value) if value is not None else None
            )
        elif field == "region":
            user.region = Region.objects.get(pk=value) if value is not None else None
        else:
            setattr(user, field, value)


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


@require_http_methods(["POST"])
def users(request):
    if not _is_admin(request):
        return _forbidden()
    payload = _body(request)
    try:
        user = User(
            username=payload["username"],
            display_name=payload.get("display_name", ""),
            role=payload["role"],
            can_publish_prices=payload.get("can_publish_prices", False),
            can_publish_crossings=payload.get("can_publish_crossings", False),
            can_view_all_complaints=payload.get("can_view_all_complaints", False),
        )
        _apply_user_fields(user, payload, ("governorate", "region"))
        if len(payload["password"]) < 12:
            raise ValidationError("كلمة المرور يجب أن تكون 12 محرفاً على الأقل.")
        user.set_password(payload["password"])
        user.full_clean()
        user.save()
    except (KeyError, User.DoesNotExist, Governorate.DoesNotExist, Region.DoesNotExist) as error:
        return JsonResponse({"detail": str(error)}, status=400)
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_user_payload(user), status=201)


@require_http_methods(["PATCH", "DELETE"])
def user_detail(request, pk):
    if not request.user.is_authenticated:
        return _forbidden()
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return JsonResponse({"detail": "Not found"}, status=404)

    if request.method == "DELETE":
        if not _is_admin(request):
            return _forbidden()
        if request.user.pk == user.pk:
            return JsonResponse({"detail": "لا يمكن حذف حسابك."}, status=400)
        if (
            user.role == User.Role.ADMIN
            and user.is_active
            and User.objects.filter(role=User.Role.ADMIN, is_active=True).count() == 1
        ):
            return JsonResponse(
                {"detail": "لا يمكن حذف آخر مدير نظام مفعّل."}, status=400
            )
        delete_user_sessions(user)
        user.delete()
        return JsonResponse({"detail": "ok"})

    if request.user.pk != user.pk and not _is_admin(request):
        return _forbidden()
    payload = json.loads(request.body or "{}")
    allowed = ("display_name",)
    if _is_admin(request):
        allowed += (
            "role",
            "governorate",
            "region",
            "can_publish_prices",
            "can_publish_crossings",
            "can_view_all_complaints",
            "is_active",
        )
    try:
        _apply_user_fields(user, payload, allowed)
        user.full_clean()
        user.save()
    except (Governorate.DoesNotExist, Region.DoesNotExist) as error:
        return JsonResponse({"detail": str(error)}, status=400)
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_user_payload(user))


@require_http_methods(["POST"])
def user_password(request, pk):
    if not request.user.is_authenticated:
        return _forbidden()
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return JsonResponse({"detail": "Not found"}, status=404)
    payload = _body(request)
    mode = payload.get("mode")

    if mode == "reset":
        if not _is_admin(request):
            return _forbidden()
        return JsonResponse({"password": reset_password(user)})

    if mode != "set":
        return JsonResponse({"detail": "Invalid password mode."}, status=400)
    if request.user.pk != user.pk and not _is_admin(request):
        return _forbidden()
    if payload.get("password") != payload.get("password_confirm"):
        return JsonResponse({"detail": "كلمتا المرور غير متطابقتين."}, status=400)
    if request.user.pk == user.pk and not user.check_password(payload.get("current_password", "")):
        return JsonResponse({"detail": "كلمة المرور الحالية غير صحيحة."}, status=400)
    try:
        set_user_password(user, payload.get("password", ""))
    except ValidationError as error:
        return _validation_error(error)
    if request.user.pk == user.pk:
        update_session_auth_hash(request, user)
    else:
        delete_user_sessions(user)
    return JsonResponse({"detail": "ok"})


@require_http_methods(["POST"])
def user_actions(request):
    if not _is_admin(request):
        return _forbidden()
    payload = _body(request)
    action = payload.get("action")
    if action not in {"activate", "deactivate"}:
        return JsonResponse({"detail": "Invalid action."}, status=400)
    succeeded, failed = [], []
    for pk in payload.get("ids", []):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            failed.append({"id": pk, "detail": "Not found"})
            continue
        user.is_active = action == "activate"
        user.save(update_fields=["is_active"])
        if action == "deactivate":
            delete_user_sessions(user)
        succeeded.append(pk)
    return JsonResponse({"succeeded": succeeded, "failed": failed})
