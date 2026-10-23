import json

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.common.listing import paginate
from apps.complaints.models import Complaint, FollowUpFile
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


def _complaint_data(complaint, detail=False):
    result = {
        "id": complaint.pk, "governorate": complaint.governorate_id,
        "region": complaint.region_id, "title": complaint.title, "body": complaint.body,
        "status": complaint.status, "inspector": complaint.inspector_id,
        "inspector_name": complaint.inspector_name, "created_at": complaint.created_at.isoformat(),
        "is_flagged": complaint.is_flagged,
    }
    if detail:
        result["follow_ups"] = [
            {
                "id": line.pk, "author_name": line.author_name, "created_at": line.created_at.isoformat(),
                "place": line.place, "body": line.body,
                "files": [{"id": item.pk, "name": item.file.name} for item in line.files.all()],
            }
            for line in complaint.follow_ups.order_by("created_at").prefetch_related("files")
        ]
    return result


@require_http_methods(["GET"])
def complaints(request):
    if _forbidden(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    queryset = visible_complaints(request.user).select_related("governorate", "region").order_by("-created_at")
    if request.GET.get("status"):
        queryset = queryset.filter(status=request.GET["status"])
    if request.user.role in {User.Role.ADMIN, User.Role.GOVERNOR} and request.GET.get("region"):
        queryset = queryset.filter(region_id=request.GET["region"])
    page = paginate(queryset, request.GET)
    page["results"] = [_complaint_data(item) for item in page["results"]]
    return JsonResponse(page)


@require_http_methods(["GET"])
def complaint_detail(request, pk):
    if _forbidden(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    complaint = visible_complaints(request.user).filter(pk=pk).first()
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
                accept_complaint(complaint, request.user, channel="web", ip=_ip(request), telegram_id=None)
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
    try:
        submit_field_report(
            complaint, request.user, request.POST.get("text", ""), request.FILES.getlist("files"),
            request.POST.get("destination"),
        )
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    return JsonResponse(_complaint_data(complaint))


@require_http_methods(["POST"])
def legal_close(request, pk):
    complaint = _visible_complaint_or_forbidden(request, pk)
    if complaint is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        close_legal(complaint, request.user, _payload(request).get("notes", ""), channel="web", ip=_ip(request), telegram_id=None)
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


