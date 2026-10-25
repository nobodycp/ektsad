from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.common.files import validate_upload
from apps.field_missions.models import (
    FieldMission,
    FieldMissionAssignee,
    FieldMissionFollowUp,
    FieldMissionFollowUpFile,
)
from apps.geography.models import Governorate


class MissionError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


def may_view(user):
    from apps.accounts.permissions import allows
    return allows(user, "can_view_field_missions")


def visible_missions(user):
    if not may_view(user):
        return FieldMission.objects.none()
    if user.role in {User.Role.ADMIN, User.Role.LEGAL, User.Role.CUSTOM}:
        return FieldMission.objects.all()
    if user.role == User.Role.GOVERNOR:
        return FieldMission.objects.filter(governorate_id=user.governorate_id)
    if user.role == User.Role.INSPECTOR:
        assigned = FieldMissionAssignee.objects.filter(mission_id=OuterRef("pk"), user=user)
        return FieldMission.objects.filter(Q(Exists(assigned)) | Q(region_id=user.region_id))
    return FieldMission.objects.none()


def _name(user):
    return user.display_name or user.username


def _required(payload):
    kind = (payload.get("kind") or "").strip()
    details = (payload.get("details") or "").strip()
    place_name = (payload.get("place_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    priority = (payload.get("priority") or "").strip()
    if kind not in FieldMission.Kind.values:
        raise MissionError("اختر نوع المهمة.")
    if priority not in FieldMission.Priority.values:
        raise MissionError("اختر أولوية المهمة.")
    if not details:
        raise MissionError("التفاصيل مطلوبة.")
    if not place_name:
        raise MissionError("اسم المحل مطلوب.")
    if not phone:
        raise MissionError("رقم الجوال مطلوب.")
    return kind, details, place_name, phone, priority


def _inspector(governorate, raw):
    if raw in (None, ""):
        raise MissionError("اختر المفتش.")
    inspector = User.objects.filter(pk=raw).first()
    if inspector is None or inspector.role != User.Role.INSPECTOR:
        raise MissionError("اختر المفتش.")
    if not inspector.is_active:
        raise MissionError("المفتش غير مفعّل.")
    if inspector.governorate_id != governorate.pk:
        raise MissionError("المفتش لا يتبع هذه المحافظة.")
    return inspector


def _assignees(user, payload):
    scope = payload.get("scope") or "one"
    if user.role == User.Role.INSPECTOR:
        return user.governorate, user.region, [user], FieldMission.Status.FIELD
    if scope == "office" and user.role not in {User.Role.ADMIN, User.Role.CUSTOM}:
        raise MissionError("هذا التوجيه لمدير النظام.")
    if user.role == User.Role.GOVERNOR:
        governorate = user.governorate
    else:
        raw = payload.get("governorate")
        if raw in (None, ""):
            raise MissionError("اختر المحافظة.")
        governorate = Governorate.objects.filter(pk=raw).first()
        if governorate is None:
            raise MissionError("اختر المحافظة.")
    if scope == "office":
        return governorate, None, [], FieldMission.Status.OFFICE
    active = User.objects.filter(role=User.Role.INSPECTOR, is_active=True, governorate=governorate)
    if scope == "all":
        inspectors = list(active.order_by("pk"))
        if not inspectors:
            raise MissionError("لا يوجد مفتش مفعّل في هذه المحافظة.")
        return governorate, None, inspectors, FieldMission.Status.FIELD
    inspector = _inspector(governorate, payload.get("inspector"))
    return governorate, inspector.region, [inspector], FieldMission.Status.FIELD


def open_mission(user, payload, image=None):
    from apps.accounts.permissions import allows
    if user.role == User.Role.LEGAL or user.role not in {
        User.Role.ADMIN, User.Role.GOVERNOR, User.Role.INSPECTOR, User.Role.CUSTOM,
    }:
        raise MissionError("هذا الدور لا يفتح مهمة ميدانية.", 403)
    if user.role != User.Role.ADMIN and not allows(user, "can_open_field_missions"):
        raise MissionError("Forbidden", 403)
    kind, details, place_name, phone, priority = _required(payload)
    if image:
        validate_upload(image, kinds={"image"})
    governorate, region, inspectors, status = _assignees(user, payload)
    with transaction.atomic():
        mission = FieldMission.objects.create(
            kind=kind,
            priority=priority,
            status=status,
            details=details,
            place_name=place_name,
            phone=phone,
            image=image,
            governorate=governorate,
            region=region,
            created_by=user,
            created_by_name=_name(user),
        )
        FieldMissionAssignee.objects.bulk_create(
            [
                FieldMissionAssignee(mission=mission, user=inspector, display_name=_name(inspector))
                for inspector in inspectors
            ]
        )
    from apps.telegram.webhook import notify_new_mission
    notify_new_mission(mission)
    return mission


def redirect_mission(user, mission, inspector_id):
    if user.role != User.Role.GOVERNOR or user.governorate_id != mission.governorate_id:
        raise MissionError("غير مسموح.", 403)
    if mission.status != FieldMission.Status.OFFICE:
        raise MissionError("أُعيد توجيه هذه المهمة.")
    inspector = _inspector(mission.governorate, inspector_id)
    with transaction.atomic():
        FieldMissionAssignee.objects.create(mission=mission, user=inspector, display_name=_name(inspector))
        FieldMissionFollowUp.objects.create(
            mission=mission,
            author=user,
            author_name=_name(user),
            place=FieldMissionFollowUp.Place.ROUTE,
            body=f"أُعيد توجيه المهمة إلى {_name(inspector)}.",
        )
        mission.region = inspector.region
        mission.status = FieldMission.Status.FIELD
        mission.save(update_fields=["region", "status"])
    return mission


def reply_mission(user, mission, text, files, destination):
    assigned = mission.assignees.filter(user=user).exists()
    if user.role != User.Role.INSPECTOR or not assigned:
        raise MissionError("غير مسموح.", 403)
    if mission.status != FieldMission.Status.FIELD:
        raise MissionError("لا يمكن الرد على هذه المهمة.")
    text = (text or "").strip()
    if not text:
        raise MissionError("نص الرد مطلوب.")
    if destination not in {"finished", "legal"}:
        raise MissionError("اختر نتيجة المهمة.")
    files = list(files or [])
    if len(files) > 5:
        raise MissionError("الحد الأقصى خمسة ملفات.")
    try:
        for upload in files:
            validate_upload(upload, kinds={"document"})
    except ValidationError as error:
        raise MissionError(error.messages[0]) from error
    now = timezone.now()
    with transaction.atomic():
        follow_up = FieldMissionFollowUp.objects.create(
            mission=mission,
            author=user,
            author_name=_name(user),
            place=FieldMissionFollowUp.Place.FIELD,
            body=text,
        )
        for upload in files:
            FieldMissionFollowUpFile.objects.create(follow_up=follow_up, file=upload)
        mission.field_replied_at = now
        if destination == "finished":
            mission.status = FieldMission.Status.FINISHED
            mission.closed_at = now
        else:
            mission.status = FieldMission.Status.LEGAL
            mission.legal_referred_at = now
        mission.save(update_fields=["field_replied_at", "status", "closed_at", "legal_referred_at"])
    return mission


def close_mission(user, mission, notes):
    if user.role != User.Role.LEGAL:
        raise MissionError("غير مسموح.", 403)
    if mission.status == FieldMission.Status.RESOLVED:
        raise MissionError("هذه المهمة مغلقة.")
    if mission.status != FieldMission.Status.LEGAL:
        raise MissionError("لا يمكن إغلاق المهمة.")
    with transaction.atomic():
        FieldMissionFollowUp.objects.create(
            mission=mission,
            author=user,
            author_name=_name(user),
            place=FieldMissionFollowUp.Place.LEGAL,
            body=(notes or "").strip() or "تم المعالجة",
        )
        mission.status = FieldMission.Status.RESOLVED
        mission.closed_at = timezone.now()
        mission.save(update_fields=["status", "closed_at"])
    return mission
