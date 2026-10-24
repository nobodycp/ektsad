import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.accounts.services import delete_user_sessions, reset_password, set_user_password
from apps.common.listing import paginate
from apps.geography.models import Governorate, Region


INVALID_CREDENTIALS = "بيانات الدخول غير صحيحة."
LAST_ADMIN_DEACTIVATE = "لا يمكن تعطيل آخر مدير نظام مفعّل."
IMPERSONATOR_SESSION_KEY = "impersonator_id"


def _body(request):
    if request.content_type == "application/json":
        return json.loads(request.body or "{}")
    return request.POST


def _last_active_admin(user):
    return (
        user.role == User.Role.ADMIN
        and user.is_active
        and not User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=user.pk).exists()
    )


@require_http_methods(["POST"])
def login_view(request):
    payload = _body(request)
    username = payload.get("username", "")
    password = payload.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": INVALID_CREDENTIALS}, status=400)
    if not user.can_login_web:
        return JsonResponse({"detail": "هذا الحساب لا يدخل من الموقع."}, status=400)
    login(request, user)
    return JsonResponse(_me_payload(user, request))


def _impersonator_payload(request):
    raw = request.session.get(IMPERSONATOR_SESSION_KEY)
    if not raw:
        return None
    admin = User.objects.filter(pk=raw, role=User.Role.ADMIN, is_active=True).first()
    if admin is None:
        return None
    return {"id": admin.pk, "username": admin.username, "display_name": admin.display_name}


def _me_payload(user, request):
    return {
        "id": user.pk,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "governorate": user.governorate_id,
        "governorate_name": user.governorate.name if user.governorate_id else None,
        "region": user.region_id,
        "region_name": user.region.name if user.region_id else None,
        "can_publish_prices": user.can_publish_prices,
        "can_publish_crossings": user.can_publish_crossings,
        "can_view_all_complaints": user.can_view_all_complaints,
        "can_login_web": user.can_login_web,
        "can_open_field_missions": user.can_open_field_missions,
        "can_view_field_missions": user.can_view_field_missions,
        "impersonator": _impersonator_payload(request),
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
        "can_login_web": user.can_login_web,
        "can_open_field_missions": user.can_open_field_missions,
        "can_view_field_missions": user.can_view_field_missions,
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
    return JsonResponse(_me_payload(request.user, request))


@require_http_methods(["POST"])
def enter_user(request, pk):
    if not _is_admin(request) or request.session.get(IMPERSONATOR_SESSION_KEY):
        return _forbidden()
    try:
        target = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return JsonResponse({"detail": "الحساب غير موجود."}, status=404)
    if target.pk == request.user.pk:
        return JsonResponse({"detail": "لا يمكن الدخول بحسابك."}, status=400)
    if not target.is_active:
        return JsonResponse({"detail": "لا يمكن الدخول بحساب معطّل."}, status=400)
    admin_id = request.user.pk
    login(request, target)
    request.session[IMPERSONATOR_SESSION_KEY] = admin_id
    return JsonResponse(_me_payload(target, request))


@require_http_methods(["POST"])
def return_session(request):
    raw = request.session.get(IMPERSONATOR_SESSION_KEY)
    if not raw:
        return JsonResponse({"detail": "لا توجد جلسة للعودة إليها."}, status=400)
    admin = User.objects.filter(pk=raw, role=User.Role.ADMIN, is_active=True).first()
    if admin is None:
        logout(request)
        return JsonResponse({"detail": "تعذّرت العودة إلى حساب المدير."}, status=400)
    login(request, admin)
    return JsonResponse(_me_payload(admin, request))


@require_http_methods(["GET", "POST"])
def users(request):
    if request.method == "GET" and request.user.is_authenticated and request.user.role == User.Role.GOVERNOR:
        queryset = User.objects.filter(
            role=User.Role.INSPECTOR, governorate_id=request.user.governorate_id, is_active=True
        )
        if request.GET.get("region"):
            queryset = queryset.filter(region_id=request.GET["region"])
        page = paginate(queryset.order_by("display_name", "username"), request.GET)
        page["results"] = [_user_payload(user) for user in page["results"]]
        return JsonResponse(page)
    if not _is_admin(request):
        return _forbidden()
    if request.method == "GET":
        queryset = User.objects.all()
        query = (request.GET.get("q") or "").strip()
        if query:
            queryset = queryset.filter(Q(username__icontains=query) | Q(display_name__icontains=query))
        if request.GET.get("role"):
            queryset = queryset.filter(role=request.GET["role"])
        if request.GET.get("governorate"):
            queryset = queryset.filter(governorate_id=request.GET["governorate"])
        active = request.GET.get("is_active")
        if active in {"1", "0", "true", "false"}:
            queryset = queryset.filter(is_active=active in {"1", "true"})
        page = paginate(queryset.order_by("username"), request.GET)
        page["results"] = [_user_payload(user) for user in page["results"]]
        return JsonResponse(page)
    payload = _body(request)
    try:
        user = User(
            username=payload["username"],
            display_name=payload.get("display_name", ""),
            role=payload["role"],
            can_publish_prices=payload.get("can_publish_prices", False),
            can_publish_crossings=payload.get("can_publish_crossings", False),
            can_view_all_complaints=payload.get("can_view_all_complaints", False),
            can_login_web=payload.get("can_login_web", True),
            can_open_field_missions=payload.get("can_open_field_missions", False),
            can_view_field_missions=payload.get("can_view_field_missions", False),
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
    if payload.get("is_active") is False and _last_active_admin(user):
        return JsonResponse({"detail": LAST_ADMIN_DEACTIVATE}, status=400)
    allowed = ("display_name",)
    if _is_admin(request):
        allowed += (
            "role",
            "governorate",
            "region",
            "can_publish_prices",
            "can_publish_crossings",
            "can_view_all_complaints",
            "can_login_web",
            "can_open_field_missions",
            "can_view_field_missions",
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
    if not user.is_active:
        delete_user_sessions(user)
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
        raw = reset_password(user)
        delete_user_sessions(user)
        return JsonResponse({"password": raw})

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
        if action == "deactivate" and _last_active_admin(user):
            failed.append({"id": pk, "detail": LAST_ADMIN_DEACTIVATE})
            continue
        user.is_active = action == "activate"
        user.save(update_fields=["is_active"])
        if action == "deactivate":
            delete_user_sessions(user)
        succeeded.append(pk)
    return JsonResponse({"succeeded": succeeded, "failed": failed})
