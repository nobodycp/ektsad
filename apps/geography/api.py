import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.geography.models import Governorate, Region


def _admin_only(request):
    return request.user.is_authenticated and getattr(request.user, "role", None) == "admin"


@require_http_methods(["GET", "POST"])
def governorates(request):
    if not _admin_only(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "POST":
        payload = json.loads(request.body or "{}")
        governorate = Governorate.objects.create(name=payload["name"])
        return JsonResponse({"id": governorate.pk, "name": governorate.name}, status=201)
    return JsonResponse(
        {"results": [{"id": item.pk, "name": item.name} for item in Governorate.objects.all()]}
    )


@require_http_methods(["GET", "POST"])
def regions(request):
    if not _admin_only(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "POST":
        payload = json.loads(request.body or "{}")
        region = Region.objects.create(
            governorate_id=payload["governorate"], name=payload["name"]
        )
        return JsonResponse(
            {"id": region.pk, "governorate": region.governorate_id, "name": region.name},
            status=201,
        )
    return JsonResponse(
        {
            "results": [
                {"id": item.pk, "governorate": item.governorate_id, "name": item.name}
                for item in Region.objects.all()
            ]
        }
    )
