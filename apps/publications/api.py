import json

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.common.files import validate_upload
from apps.common.listing import paginate
from apps.publications.models import CrossingReport, PriceReport


def _payload(request):
    if request.content_type and request.content_type.startswith("application/json"):
        return json.loads(request.body or "{}")
    return request.POST


def _publisher_name(user):
    return user.display_name or user.username


def _can_list(user, flag):
    return user.is_authenticated and (user.role == User.Role.ADMIN or getattr(user, flag))


def _can_publish(user, flag):
    return user.is_authenticated and getattr(user, flag)


def _price_data(report):
    return {
        "id": report.pk,
        "published_at": report.published_at.isoformat(),
        "publisher_name": report.publisher_name,
        "has_image": bool(report.image),
    }


def _crossing_data(report):
    return {
        "id": report.pk,
        "published_at": report.published_at.isoformat(),
        "publisher_name": report.publisher_name,
        "body": report.body,
        "has_image": bool(report.image),
    }


@require_http_methods(["GET", "POST"])
def prices(request):
    if request.method == "GET":
        if not _can_list(request.user, "can_publish_prices"):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        page = paginate(PriceReport.objects.order_by("-published_at"), request.GET)
        page["results"] = [_price_data(report) for report in page["results"]]
        return JsonResponse(page)

    if not _can_publish(request.user, "can_publish_prices"):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    image = request.FILES.get("image")
    if image is None:
        return JsonResponse({"detail": "الصورة مطلوبة."}, status=400)
    try:
        validate_upload(image, kinds={"image"})
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    report = PriceReport.objects.create(
        image=image, publisher=request.user, publisher_name=_publisher_name(request.user)
    )
    return JsonResponse(_price_data(report), status=201)


@require_http_methods(["GET", "POST"])
def crossings(request):
    if request.method == "GET":
        if not _can_list(request.user, "can_publish_crossings"):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        page = paginate(CrossingReport.objects.order_by("-published_at"), request.GET)
        page["results"] = [_crossing_data(report) for report in page["results"]]
        return JsonResponse(page)

    if not _can_publish(request.user, "can_publish_crossings"):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    payload = _payload(request)
    body = payload.get("body") or ""
    if not isinstance(body, str):
        body = str(body)
    image = request.FILES.get("image")
    if not body.strip() and image is None:
        return JsonResponse({"detail": "يجب إدخال النص أو إرفاق صورة."}, status=400)
    try:
        if image is not None:
            validate_upload(image, kinds={"image"})
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    report = CrossingReport.objects.create(
        body=body, image=image, publisher=request.user, publisher_name=_publisher_name(request.user)
    )
    return JsonResponse(_crossing_data(report), status=201)


@require_http_methods(["GET"])
def latest_price(request):
    report = PriceReport.objects.order_by("-published_at").first()
    if report is None:
        return JsonResponse({"detail": "لا توجد قائمة أسعار منشورة."})
    return JsonResponse(_price_data(report))


@require_http_methods(["GET"])
def latest_crossing(request):
    report = CrossingReport.objects.order_by("-published_at").first()
    if report is None:
        return JsonResponse({"detail": "لا توجد حركة معابر منشورة."})
    return JsonResponse(_crossing_data(report))


@require_http_methods(["GET"])
def latest_price_media(request):
    report = PriceReport.objects.order_by("-published_at").first()
    if report is None or not report.image:
        raise Http404
    return FileResponse(report.image.open("rb"))


@require_http_methods(["GET"])
def latest_crossing_media(request):
    report = CrossingReport.objects.order_by("-published_at").first()
    if report is None or not report.image:
        raise Http404
    return FileResponse(report.image.open("rb"))
