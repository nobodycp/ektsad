import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.common.listing import paginate
from apps.geography.models import Governorate, Region
from apps.geography.services import delete_governorate, delete_region


NAME_TAKEN = "الاسم مستخدم."


def _admin_only(request):
    return request.user.is_authenticated and getattr(request.user, "role", None) == "admin"


@require_http_methods(["GET"])
def public_governorates(request):
    page = paginate(Governorate.objects.order_by("name"), request.GET)
    page["results"] = [{"id": item.pk, "name": item.name} for item in page["results"]]
    return JsonResponse(page)


@require_http_methods(["GET"])
def public_regions(request):
    queryset = Region.objects.select_related("governorate").order_by("name")
    governorate = request.GET.get("governorate")
    if governorate:
        queryset = queryset.filter(governorate_id=governorate)
    page = paginate(queryset, request.GET)
    page["results"] = [
        {"id": item.pk, "governorate": item.governorate_id, "name": item.name}
        for item in page["results"]
    ]
    return JsonResponse(page)


@require_http_methods(["GET", "POST"])
def governorates(request):
    if not _admin_only(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "POST":
        payload = json.loads(request.body or "{}")
        name = str(payload.get("name") or "").strip()
        if not name:
            return JsonResponse({"detail": "الاسم مطلوب."}, status=400)
        try:
            with transaction.atomic():
                governorate = Governorate.objects.create(name=name)
        except IntegrityError:
            return JsonResponse({"detail": NAME_TAKEN}, status=400)
        return JsonResponse({"id": governorate.pk, "name": governorate.name}, status=201)
    page = paginate(Governorate.objects.all(), request.GET)
    page["results"] = [{"id": item.pk, "name": item.name} for item in page["results"]]
    return JsonResponse(page)


@require_http_methods(["GET", "POST"])
def regions(request):
    if not _admin_only(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "POST":
        payload = json.loads(request.body or "{}")
        name = str(payload.get("name") or "").strip()
        if not name:
            return JsonResponse({"detail": "الاسم مطلوب."}, status=400)
        try:
            with transaction.atomic():
                region = Region.objects.create(governorate_id=payload["governorate"], name=name)
        except (IntegrityError, KeyError, ValueError, TypeError):
            return JsonResponse({"detail": NAME_TAKEN}, status=400)
        return JsonResponse(
            {"id": region.pk, "governorate": region.governorate_id, "name": region.name},
            status=201,
        )
    queryset = Region.objects.select_related("governorate")
    if request.GET.get("governorate"):
        queryset = queryset.filter(governorate_id=request.GET["governorate"])
    page = paginate(queryset, request.GET)
    page["results"] = [
        {"id": item.pk, "governorate": item.governorate_id, "name": item.name}
        for item in page["results"]
    ]
    return JsonResponse(page)


def _rename(instance, payload):
    name = str(payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"detail": "الاسم مطلوب."}, status=400)
    instance.name = name
    try:
        with transaction.atomic():
            instance.save(update_fields=["name"])
    except IntegrityError:
        return JsonResponse({"detail": NAME_TAKEN}, status=400)
    return JsonResponse({"id": instance.pk, "name": instance.name})


@require_http_methods(["PATCH", "DELETE"])
def governorate_detail(request, pk):
    if not _admin_only(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    governorate = Governorate.objects.filter(pk=pk).first()
    if governorate is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    if request.method == "DELETE":
        try:
            delete_governorate(pk)
        except ValidationError as error:
            return JsonResponse({"detail": error.messages[0]}, status=400)
        return JsonResponse({"detail": "ok"})
    return _rename(governorate, json.loads(request.body or "{}"))


@require_http_methods(["PATCH", "DELETE"])
def region_detail(request, pk):
    if not _admin_only(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    region = Region.objects.filter(pk=pk).first()
    if region is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    if request.method == "DELETE":
        try:
            delete_region(pk)
        except ValidationError as error:
            return JsonResponse({"detail": error.messages[0]}, status=400)
        return JsonResponse({"detail": "ok"})
    return _rename(region, json.loads(request.body or "{}"))
