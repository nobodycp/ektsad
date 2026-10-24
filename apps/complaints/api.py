import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.common.files import validate_upload
from apps.common.listing import paginate
from apps.complaints.models import Complaint, FollowUp, FollowUpFile
from apps.geography.models import Region
from apps.complaints.services import (
    accept_complaint,
    assign_complaint,
    close_legal,
    submit_field_report,
    visible_complaints,
)


def _payload(request):
    if request.content_type and request.content_type.startswith("application/json"):
        return json.loads(request.body or "{}")
    return request.POST


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _forbidden(request):
    return not request.user.is_authenticated


PUBLIC_RATE_LIMIT_MESSAGE = "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً."


def _iso(value):
    return value.isoformat() if value else None


def _with_field_time(queryset):
    field_at = FollowUp.objects.filter(
        complaint=OuterRef("pk"), place=FollowUp.Place.FIELD
    ).order_by("created_at").values("created_at")[:1]
    return queryset.annotate(field_replied_at=Subquery(field_at))


def _complaint_data(complaint, detail=False):
    result = {
        "id": complaint.pk, "governorate": complaint.governorate_id,
        "governorate_name": complaint.governorate.name,
        "region": complaint.region_id, "region_name": complaint.region.name,
        "title": complaint.title, "body": complaint.body,
        "status": complaint.status, "inspector": complaint.inspector_id,
        "inspector_name": complaint.inspector_name, "created_at": complaint.created_at.isoformat(),
        "is_flagged": complaint.is_flagged,
        "source": complaint.source,
        "submitter_ip": complaint.submitter_ip,
        "telegram_user_id": complaint.telegram_user_id,
        "has_image": bool(complaint.image),
        "field_replied_at": _iso(getattr(complaint, "field_replied_at", None)),
    }
    if detail:
        result.update({
            "accepted_at": _iso(complaint.accepted_at),
            "legal_referred_at": _iso(complaint.legal_referred_at),
            "closed_at": _iso(complaint.closed_at),
            "assigned_by_name": complaint.assigned_by_name,
        })
        result["follow_ups"] = [
            {
                "id": line.pk, "author_name": line.author_name, "created_at": line.created_at.isoformat(),
                "place": line.place, "body": line.body,
                "files": [{"id": item.pk, "name": item.file.name} for item in line.files.all()],
            }
            for line in complaint.follow_ups.order_by("created_at").prefetch_related("files")
        ]
    return result


def _iso_day(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValidationError("تاريخ غير صالح.") from error


def _apply_day_filters(queryset, params):
    hebron = ZoneInfo("Asia/Hebron")

    def bounds(day):
        start = datetime.combine(day, time.min, tzinfo=hebron)
        return start, start + timedelta(days=1)

    created_from = _iso_day(params.get("created_from"))
    created_to = _iso_day(params.get("created_to"))
    closed_from = _iso_day(params.get("closed_from"))
    closed_to = _iso_day(params.get("closed_to"))
    if created_from:
        queryset = queryset.filter(created_at__gte=bounds(created_from)[0])
    if created_to:
        queryset = queryset.filter(created_at__lt=bounds(created_to)[1])
    if closed_from:
        queryset = queryset.filter(closed_at__gte=bounds(closed_from)[0], status__in=("منتهية", "تم المعالجه خلص"))
    if closed_to:
        queryset = queryset.filter(closed_at__lt=bounds(closed_to)[1], status__in=("منتهية", "تم المعالجه خلص"))
    return queryset


@require_http_methods(["GET"])
def complaints(request):
    if _forbidden(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    queryset = _with_field_time(
        visible_complaints(request.user).select_related("governorate", "region")
    ).order_by("-created_at")
    if request.GET.get("status"):
        queryset = queryset.filter(status=request.GET["status"])
    if request.GET.get("flagged") == "1":
        queryset = queryset.filter(is_flagged=True)
    try:
        queryset = _apply_day_filters(queryset, request.GET)
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    if request.user.role in {User.Role.ADMIN, User.Role.GOVERNOR} and request.GET.get("region"):
        queryset = queryset.filter(region_id=request.GET["region"])
    page = paginate(queryset, request.GET)
    page["results"] = [_complaint_data(item) for item in page["results"]]
    return JsonResponse(page)


@require_http_methods(["GET"])
def complaint_detail(request, pk):
    if _forbidden(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    complaint = _with_field_time(visible_complaints(request.user)).filter(pk=pk).first()
    if complaint is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse(_complaint_data(complaint, detail=True))


@require_http_methods(["POST"])
def complaint_actions(request):
    if _forbidden(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    payload = _payload(request)
    action, ids = payload.get("action"), payload.get("ids", [])
    if action == "accept":
        if request.user.role != User.Role.INSPECTOR:
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if len(ids) != 1:
            return JsonResponse({"detail": "يجب اختيار شكوى واحدة."}, status=400)
    elif action in {"flag", "unflag"}:
        if request.user.role not in {User.Role.ADMIN, User.Role.GOVERNOR}:
            return JsonResponse({"detail": "Forbidden"}, status=403)
    else:
        return JsonResponse({"detail": "طلب غير صالح."}, status=400)
    succeeded, failed = [], []
    for pk in ids:
        complaint = Complaint.objects.filter(pk=pk).first()
        try:
            if complaint is None:
                raise ValidationError("الشكوى غير موجودة.")
            if action == "accept":
                with transaction.atomic():
                    accept_complaint(complaint, request.user, channel="web", ip=_ip(request), telegram_id=None)
                    from apps.telegram.webhook import notify_accept
                    notify_accept(complaint, request.user)
            else:
                if request.user.role == User.Role.GOVERNOR and complaint.governorate_id != request.user.governorate_id:
                    raise ValidationError("غير مسموح.")
                complaint.is_flagged = action == "flag"
                complaint.flagged_by = request.user if action == "flag" else None
                complaint.flagged_at = timezone.now() if action == "flag" else None
                complaint.save()
            succeeded.append(pk)
        except ValidationError as error:
            failed.append({"id": pk, "detail": error.messages[0]})
    return JsonResponse({"succeeded": succeeded, "failed": failed})


def _visible_complaint_or_forbidden(request, pk):
    if _forbidden(request):
        return None
    return visible_complaints(request.user).filter(pk=pk).first()


@require_http_methods(["POST"])
def assign(request, pk):
    complaint = _visible_complaint_or_forbidden(request, pk)
    if complaint is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    payload = _payload(request)
    try:
        inspector = User.objects.get(pk=payload.get("inspector"))
        assign_complaint(complaint, request.user, inspector, channel="web", ip=_ip(request), telegram_id=None)
    except (User.DoesNotExist, ValidationError) as error:
        return JsonResponse({"detail": getattr(error, "messages", ["المفتش غير صالح."])[0]}, status=400)
    return JsonResponse(_complaint_data(complaint))


@require_http_methods(["POST"])
def field_report(request, pk):
    complaint = _visible_complaint_or_forbidden(request, pk)
    if complaint is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    destination = request.POST.get("destination")
    try:
        with transaction.atomic():
            submit_field_report(
                complaint, request.user, request.POST.get("text", ""), request.FILES.getlist("files"),
                destination, channel="web", ip=_ip(request),
            )
            if destination == "governor":
                from apps.telegram.webhook import notify_citizen_resolved
                notify_citizen_resolved(complaint)
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    return JsonResponse(_complaint_data(complaint))


@require_http_methods(["POST"])
def legal_close(request, pk):
    complaint = _visible_complaint_or_forbidden(request, pk)
    if complaint is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        with transaction.atomic():
            close_legal(complaint, request.user, _payload(request).get("notes", ""), channel="web", ip=_ip(request), telegram_id=None)
            from apps.telegram.webhook import notify_citizen_resolved
            notify_citizen_resolved(complaint)
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    return JsonResponse(_complaint_data(complaint))


@require_http_methods(["GET"])
def complaint_media(request, pk):
    complaint = _visible_complaint_or_forbidden(request, pk)
    if complaint is None or not complaint.image:
        raise Http404
    return FileResponse(complaint.image.open("rb"))


@require_http_methods(["GET"])
def followup_media(request, pk, file_id):
    complaint = _visible_complaint_or_forbidden(request, pk)
    item = FollowUpFile.objects.filter(pk=file_id, follow_up__complaint_id=pk).first()
    if complaint is None or item is None:
        raise Http404
    return FileResponse(item.file.open("rb"))


@require_http_methods(["POST"])
def public_complaint(request):
    from apps.common.models import SystemSettings

    if not SystemSettings.current().web_complaints_enabled:
        return JsonResponse({"detail": "تقديم الشكاوى عبر الموقع متوقف حالياً."}, status=403)
    payload = _payload(request)
    try:
        region = Region.objects.get(pk=payload.get("region"))
        if region.governorate_id != int(payload.get("governorate")):
            raise ValidationError("المنطقة لا تتبع المحافظة.")
        image = request.FILES.get("image")
        if image:
            validate_upload(image, kinds={"image"})
    except (Region.DoesNotExist, TypeError, ValueError, ValidationError) as error:
        detail = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        return JsonResponse({"detail": detail}, status=400)
    ip = _ip(request) or ""
    key = f"complaint-public-rate:{ip}"
    if cache.add(key, 1, timeout=3600):
        count = 1
    else:
        count = cache.incr(key)
    if count > 10:
        return JsonResponse({"detail": PUBLIC_RATE_LIMIT_MESSAGE}, status=429)
    with transaction.atomic():
        complaint = Complaint.objects.create(
            governorate_id=region.governorate_id, region=region, title=payload.get("title", ""),
            body=payload.get("body", ""), image=image, source=Complaint.Source.WEB, submitter_ip=ip or None,
        )
        from apps.telegram.webhook import notify_new_complaint
        notify_new_complaint(complaint)
    return JsonResponse({"detail": "تم استلام الشكوى."}, status=201)


