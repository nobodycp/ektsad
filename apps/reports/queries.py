from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone

from django.db.models.functions import TruncDate

from apps.accounts.models import User
from apps.complaints.models import Complaint, FollowUp
from apps.complaints.services import visible_complaints
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


TREND_LIMIT_DAYS = 92
OPEN_STATUSES = (
    Complaint.Status.RECEIVED,
    Complaint.Status.FIELD,
    Complaint.Status.LEGAL,
)


def _change_percent(current, previous):
    if previous <= 0:
        return None
    return round((current - previous) * 100 / previous)


def _day_key(value):
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _counts_by_day(queryset, field, start, end):
    rows = (
        queryset.filter(**{f"{field}__gte": start, f"{field}__lt": end})
        .annotate(day=TruncDate(field, tzinfo=HEBRON))
        .values("day")
        .annotate(count=Count("id"))
    )
    return {_day_key(row["day"]): row["count"] for row in rows}


def _overview_scope(user, params):
    queryset = visible_complaints(user)
    if user.role == User.Role.ADMIN:
        return queryset.filter(**_geo_filters(params))
    if user.role == User.Role.GOVERNOR:
        filters = _geo_filters({"governorate": user.governorate_id, "region": params.get("region")})
        return queryset.filter(**filters)
    return queryset


def _overview_period(params):
    if not params.get("date_from") and not params.get("date_to"):
        today = _today()
        params = {
            **params,
            "date_from": (today - timedelta(days=6)).isoformat(),
            "date_to": today.isoformat(),
        }
    return _period(params)


def overview(user, params):
    start_day, end_day, start, end = _overview_period(params)
    span = (end_day - start_day).days + 1
    previous_end_day = start_day - timedelta(days=1)
    previous_start_day = previous_end_day - timedelta(days=span - 1)
    previous_start, _ = _day_bounds(previous_start_day)
    _, previous_end = _day_bounds(previous_end_day)
    scope = _overview_scope(user, params)

    by_status = {status.value: 0 for status in Complaint.Status}
    for row in scope.values("status").annotate(count=Count("id")):
        by_status[row["status"]] = row["count"]
    total = sum(by_status.values())
    done_now = by_status[Complaint.Status.FINISHED] + by_status[Complaint.Status.RESOLVED]
    remaining = total - done_now

    created = scope.filter(created_at__gte=start, created_at__lt=end).count()
    created_previous = scope.filter(created_at__gte=previous_start, created_at__lt=previous_end).count()
    done = scope.filter(closed_at__gte=start, closed_at__lt=end, status__in=DONE_STATUSES).count()
    done_previous = scope.filter(
        closed_at__gte=previous_start, closed_at__lt=previous_end, status__in=DONE_STATUSES
    ).count()
    pending_at_end = _pending(scope, end).count()
    pending_previous = _pending(scope, previous_end).count()

    trend = None
    trend_note = None
    if span > TREND_LIMIT_DAYS:
        trend_note = "الرسم اليومي متاح حتى 92 يوماً."
    else:
        created_by_day = _counts_by_day(scope, "created_at", start, end)
        done_by_day = _counts_by_day(
            scope.filter(status__in=DONE_STATUSES), "closed_at", start, end
        )
        trend = []
        day = start_day
        while day <= end_day:
            trend.append({
                "date": day.isoformat(),
                "created": created_by_day.get(day, 0),
                "done": done_by_day.get(day, 0),
            })
            day += timedelta(days=1)

    attention = []
    for status in OPEN_STATUSES:
        if by_status[status]:
            attention.append({"kind": "status", "status": status, "count": by_status[status]})
    flagged = scope.filter(is_flagged=True).count()
    if flagged and user.role in {User.Role.ADMIN, User.Role.GOVERNOR}:
        attention.append({"kind": "flagged", "count": flagged})

    inspectors = None
    if user.role in {User.Role.ADMIN, User.Role.GOVERNOR}:
        people = User.objects.filter(role=User.Role.INSPECTOR)
        if user.role == User.Role.GOVERNOR:
            people = people.filter(governorate_id=user.governorate_id)
        else:
            geo = _geo_filters(params)
            if geo.get("governorate_id"):
                people = people.filter(governorate_id=geo["governorate_id"])
            if geo.get("region_id"):
                people = people.filter(region_id=geo["region_id"])
        inspectors = [
            {
                "id": person.pk,
                "name": person.display_name or person.username,
                "done": scope.filter(
                    inspector=person, closed_at__gte=start, closed_at__lt=end, status__in=DONE_STATUSES
                ).count(),
            }
            for person in people.order_by("pk")
        ]

    publications = {}
    if user.role == User.Role.ADMIN or user.can_publish_prices:
        publications["prices"] = PriceReport.objects.filter(published_at__gte=start, published_at__lt=end).count()
    if user.role == User.Role.ADMIN or user.can_publish_crossings:
        publications["crossings"] = CrossingReport.objects.filter(published_at__gte=start, published_at__lt=end).count()

    recent = [
        {
            "id": row.id,
            "title": row.title,
            "status": row.status,
            "region_name": row.region.name,
            "created_at": row.created_at.isoformat(),
        }
        for row in scope.select_related("region").order_by("-created_at")[:5]
    ]

    return {
        "period": {
            "from": start_day.isoformat(),
            "to": end_day.isoformat(),
            "previous_from": previous_start_day.isoformat(),
            "previous_to": previous_end_day.isoformat(),
        },
        "current": {
            "total": total,
            "done": done_now,
            "remaining": remaining,
            "percent_done": None if total == 0 else round(done_now * 100 / total),
            "by_status": by_status,
        },
        "period_metrics": {
            "created": created,
            "created_previous": created_previous,
            "created_delta": created - created_previous,
            "created_percent": _change_percent(created, created_previous),
            "done": done,
            "done_previous": done_previous,
            "done_delta": done - done_previous,
            "done_percent": _change_percent(done, done_previous),
            "pending_at_end": pending_at_end,
            "pending_previous": pending_previous,
            "pending_delta": pending_at_end - pending_previous,
            "pending_percent": _change_percent(pending_at_end, pending_previous),
            "legal_referred": scope.filter(legal_referred_at__gte=start, legal_referred_at__lt=end).count(),
            "legal_resolved": scope.filter(
                closed_at__gte=start, closed_at__lt=end, status=Complaint.Status.RESOLVED
            ).count(),
            "still_legal": scope.filter(legal_referred_at__lt=end).filter(
                Q(closed_at__isnull=True) | Q(closed_at__gte=end)
            ).count(),
        },
        "trend": trend,
        "trend_note": trend_note,
        "attention": attention,
        "inspectors": inspectors,
        "publications": publications or None,
        "recent": recent,
    }
