from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import models
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.accounts.models import User
from apps.common.files import validate_upload
from apps.complaints.models import Complaint, ComplaintSeen, FollowUp, FollowUpFile


def _name(user):
    return user.display_name or user.username


def accept_complaint(complaint, actor, *, channel, ip, telegram_id):
    if complaint.status != Complaint.Status.RECEIVED:
        if complaint.inspector_id and complaint.inspector_id != actor.pk:
            raise ValidationError("استلم هذه الشكوى مفتش آخر.")
        raise ValidationError("لا يمكن استلام الشكوى.")
    if actor.role != User.Role.INSPECTOR or actor.region_id != complaint.region_id:
        raise ValidationError("غير مسموح.")
    complaint.inspector = actor
    complaint.inspector_name = _name(actor)
    complaint.status = Complaint.Status.FIELD
    complaint.accepted_at = timezone.now()
    complaint.accept_ip = ip
    complaint.accept_channel = channel
    complaint.save()


def assign_complaint(complaint, actor, inspector, *, channel, ip, telegram_id):
    if complaint.status != Complaint.Status.RECEIVED:
        raise ValidationError("لا يمكن تعيين الشكوى.")
    if actor.role != User.Role.GOVERNOR or actor.governorate_id != complaint.governorate_id:
        raise ValidationError("غير مسموح.")
    if (
        inspector.role != User.Role.INSPECTOR or not inspector.is_active
        or inspector.governorate_id != complaint.governorate_id
        or inspector.region_id != complaint.region_id
    ):
        raise ValidationError("المفتش غير صالح.")
    complaint.inspector = inspector
    complaint.inspector_name = _name(inspector)
    complaint.assigned_by = actor
    complaint.assigned_by_name = _name(actor)
    complaint.status = Complaint.Status.FIELD
    complaint.accepted_at = timezone.now()
    complaint.accept_ip = ip
    complaint.accept_channel = channel
    complaint.save()


@transaction.atomic
def submit_field_report(complaint, actor, text, files, destination, *, channel="web", ip=None, telegram_id=""):
    if actor.role != User.Role.INSPECTOR or complaint.inspector_id != actor.pk:
        raise ValidationError("غير مسموح.")
    if complaint.status != Complaint.Status.FIELD or not text or not text.strip():
        raise ValidationError("نص المتابعة مطلوب.")
    if destination not in {"governor", "legal"}:
        raise ValidationError("وجهة غير صالحة.")
    files = list(files)
    if len(files) > 5:
        raise ValidationError("الحد الأقصى خمسة ملفات.")
    for upload in files:
        validate_upload(upload, kinds={"document"})
    follow_up = FollowUp.objects.create(
        complaint=complaint, author=actor, author_name=_name(actor),
        place=FollowUp.Place.FIELD, body=text.strip(),
        channel=channel, author_ip=ip, author_telegram_id=telegram_id or "",
    )
    for upload in files:
        FollowUpFile.objects.create(follow_up=follow_up, file=upload)
    if destination == "governor":
        complaint.status = Complaint.Status.FINISHED
        complaint.closed_at = timezone.now()
    else:
        complaint.status = Complaint.Status.LEGAL
        complaint.legal_referred_at = timezone.now()
    complaint.save()


def close_legal(complaint, actor, notes, *, channel, ip, telegram_id):
    if actor.role != User.Role.LEGAL:
        raise ValidationError("غير مسموح.")
    if complaint.status == Complaint.Status.RESOLVED:
        raise ValidationError("هذه الشكوى مغلقة.")
    if complaint.status != Complaint.Status.LEGAL:
        raise ValidationError("لا يمكن إغلاق الشكوى.")
    FollowUp.objects.create(
        complaint=complaint, author=actor, author_name=_name(actor),
        place=FollowUp.Place.LEGAL, body=(notes or "").strip() or "تم الانجاز",
        channel=channel, author_ip=ip, author_telegram_id=telegram_id or "",
    )
    complaint.status = Complaint.Status.RESOLVED
    complaint.closed_at = timezone.now()
    complaint.save()


def unread_incoming(user):
    seen = ComplaintSeen.objects.filter(user=user, complaint_id=OuterRef("pk"))
    return (
        visible_complaints(user)
        .filter(status=Complaint.Status.RECEIVED)
        .annotate(_seen=Exists(seen))
        .filter(_seen=False)
    )


def mark_complaint_seen(user, complaint):
    ComplaintSeen.objects.get_or_create(user=user, complaint=complaint)


def visible_complaints(user):
    queryset = Complaint.objects.all()
    if not user.is_authenticated:
        return queryset.none()
    if user.can_view_all_complaints or user.role == User.Role.ADMIN:
        return queryset
    if user.role == User.Role.INSPECTOR:
        return queryset.filter(
            models.Q(region_id=user.region_id, status=Complaint.Status.RECEIVED)
            | models.Q(inspector_id=user.pk)
        )
    if user.role == User.Role.GOVERNOR:
        return queryset.filter(governorate_id=user.governorate_id)
    if user.role == User.Role.LEGAL:
        return queryset.filter(legal_referred_at__isnull=False)
    return queryset.none()
