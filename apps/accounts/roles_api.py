import json

from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import StaffRole
from apps.accounts.permissions import ROLE_FIELDS


def _admin(request):
    user = request.user
    return user.is_authenticated and user.role == "admin"


def _can_list(request):
    from apps.accounts.permissions import allows
    return request.user.is_authenticated and allows(request.user, "can_manage_users")


def _body(request):
    if request.content_type == "application/json":
        return json.loads(request.body or "{}")
    return request.POST


def _payload(role):
    data = {"id": role.pk, "name": role.name, "kind": role.kind, "built_in": role.built_in}
    for field in ROLE_FIELDS:
        data[field] = getattr(role, field)
    return data


def _apply(role, payload):
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            return "اسم الدور مطلوب."
        if StaffRole.objects.exclude(pk=role.pk).filter(name=name).exists():
            return "اسم الدور مستخدم."
        role.name = name
    for field in ROLE_FIELDS:
        if field in payload:
            setattr(role, field, bool(payload[field]))
    return None


@require_http_methods(["GET", "POST"])
def roles(request):
    if request.method == "GET":
        if not _can_list(request):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        rows = StaffRole.objects.order_by("built_in", "pk")
        return JsonResponse({"results": [_payload(role) for role in rows]})
    if not _admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    payload = _body(request)
    role = StaffRole(kind=StaffRole.Kind.CUSTOM, built_in=False, name="")
    error = _apply(role, {"name": payload.get("name"), **{field: payload[field] for field in ROLE_FIELDS if field in payload}})
    if error:
        return JsonResponse({"detail": error}, status=400)
    try:
        role.save()
    except IntegrityError:
        return JsonResponse({"detail": "اسم الدور مستخدم."}, status=400)
    return JsonResponse(_payload(role), status=201)


@require_http_methods(["PATCH", "DELETE"])
def role_detail(request, pk):
    if not _admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    role = StaffRole.objects.filter(pk=pk).first()
    if role is None:
        return JsonResponse({"detail": "الدور غير موجود."}, status=404)
    if request.method == "DELETE":
        if role.built_in:
            return JsonResponse({"detail": "لا يمكن حذف هذا الدور."}, status=400)
        if role.members.exists():
            return JsonResponse({"detail": "هذا الدور مرتبط بمستخدمين."}, status=400)
        role.delete()
        return JsonResponse({"detail": "ok"})
    error = _apply(role, _body(request))
    if error:
        return JsonResponse({"detail": error}, status=400)
    try:
        role.save()
    except IntegrityError:
        return JsonResponse({"detail": "اسم الدور مستخدم."}, status=400)
    return JsonResponse(_payload(role))
