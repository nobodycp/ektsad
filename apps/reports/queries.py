from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.complaints.models import Complaint, FollowUp
from apps.geography.models import Region
from apps.publications.models import CrossingReport, PriceReport


HEBRON = ZoneInfo("Asia/Hebron")
DONE_STATUSES = (Complaint.Status.FINISHED, Complaint.Status.RESOLVED)


def _today():
    return timezone.now().astimezone(HEBRON).date()


def _day_bounds(day):
    start = datetime.combine(day, time.min, tzinfo=HEBRON)
    return start, start + timedelta(days=1)


def _date_value(value, default):
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValidationError("تاريخ غير صالح.") from error


def _period(params):
    today = _today()
    start_day = _date_value(params.get("date_from"), today)
    end_day = _date_value(params.get("date_to"), today)
    if start_day > end_day:
        raise ValidationError("تاريخ البداية بعد تاريخ النهاية.")
    start, _ = _day_bounds(start_day)
    _, end = _day_bounds(end_day)
    return start_day, end_day, start, end


def _optional_id(value, message):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(message) from error
    if parsed < 1:
        raise ValidationError(message)
    return parsed


def _geo_filters(params):
    governorate_id = _optional_id(params.get("governorate"), "المحافظة غير صالحة.")
    region_id = _optional_id(params.get("region"), "المنطقة غير صالحة.")
    inspector_id = _optional_id(params.get("inspector"), "المفتش غير صالح.")
    if governorate_id and region_id:
        belongs_to_governorate = Region.objects.filter(
            pk=region_id, governorate_id=governorate_id
        ).exists()
        if not belongs_to_governorate:
            raise ValidationError("المنطقة لا تتبع المحافظة.")
    filters = {}
    if governorate_id:
        filters["governorate_id"] = governorate_id
    if region_id:
        filters["region_id"] = region_id
    if inspector_id:
        filters["inspector_id"] = inspector_id
    return filters


def _pending(queryset, end):
    return queryset.filter(accepted_at__lt=end).filter(
        Q(closed_at__isnull=True) | Q(closed_at__gte=end)
    )


def governor_daily(governorate, day):
    start, end = _day_bounds(day)
    complaints = Complaint.objects.filter(governorate=governorate)
    done = complaints.filter(closed_at__gte=start, closed_at__lt=end, status__in=DONE_STATUSES)
    done_by_inspector = {
        row["author_name"]: row["count"]
        for row in FollowUp.objects.filter(
            complaint__in=done, place=FollowUp.Place.FIELD
        ).values("author_name").annotate(count=Count("complaint", distinct=True))
    }
    return {
        "date": day.isoformat(),
        "done": done.count(),
        "pending": _pending(complaints, end).count(),
        "done_by_inspector": done_by_inspector,
    }


def admin_report(params):
    _, _, start, end = _period(params)
    geo_filters = _geo_filters(params)
    complaints = Complaint.objects.filter(**geo_filters)
    complaints_in_period = complaints.filter(created_at__gte=start, created_at__lt=end)
    complaint_filters = complaints_in_period
    if params.get("status"):
        complaint_filters = complaint_filters.filter(status=params["status"])

    inspectors = User.objects.filter(role=User.Role.INSPECTOR)
    if geo_filters.get("governorate_id"):
        inspectors = inspectors.filter(governorate_id=geo_filters["governorate_id"])
    if geo_filters.get("region_id"):
        inspectors = inspectors.filter(region_id=geo_filters["region_id"])
    if geo_filters.get("inspector_id"):
        inspectors = inspectors.filter(pk=geo_filters["inspector_id"])

    inspector_rows = []
    for inspector in inspectors.order_by("pk"):
        assigned = complaints.filter(inspector=inspector)
        durations = [
            follow_up.created_at - follow_up.complaint.accepted_at
            for follow_up in FollowUp.objects.filter(
                complaint__in=assigned,
                author=inspector,
                place=FollowUp.Place.FIELD,
                created_at__gte=start,
                created_at__lt=end,
                complaint__accepted_at__isnull=False,
            ).select_related("complaint")
        ]
        average = None
        if durations:
            total_seconds = sum(duration.total_seconds() for duration in durations)
            total_minutes = int(total_seconds / len(durations) // 60)
            average = {"hours": total_minutes // 60, "minutes": total_minutes % 60}
        inspector_rows.append({
            "id": inspector.pk,
            "name": inspector.display_name or inspector.username,
            "accepted": assigned.filter(accepted_at__gte=start, accepted_at__lt=end).count(),
            "done": assigned.filter(
                closed_at__gte=start, closed_at__lt=end, status__in=DONE_STATUSES
            ).count(),
            "pending": _pending(assigned, end).count(),
            "average": average,
        })

    legal = {
        "referred": complaints.filter(legal_referred_at__gte=start, legal_referred_at__lt=end).count(),
        "resolved": complaints.filter(
            closed_at__gte=start, closed_at__lt=end, status=Complaint.Status.RESOLVED
        ).count(),
        "still_legal": complaints.filter(legal_referred_at__lt=end).filter(
            Q(closed_at__isnull=True) | Q(closed_at__gte=end)
        ).count(),
    }
    return {
        "complaints": {
            "count": complaint_filters.count(),
            "by_status": {
                row["status"]: row["count"]
                for row in complaint_filters.values("status").annotate(count=Count("id"))
            },
        },
        "inspectors": inspector_rows,
        "legal": legal,
        "publications": {
            "prices": PriceReport.objects.filter(published_at__gte=start, published_at__lt=end).count(),
            "crossings": CrossingReport.objects.filter(published_at__gte=start, published_at__lt=end).count(),
        },
    }
