from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from apps.accounts.models import User
from apps.common.files import validate_upload
from apps.field_missions.models import FieldMission, FieldMissionAssignee
from apps.geography.models import Governorate


class MissionError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


def may_view(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.role == User.Role.ADMIN:
        return True
    return bool(user.can_view_field_missions)


def visible_missions(user):
    if not may_view(user):
        return FieldMission.objects.none()
    if user.role in {User.Role.ADMIN, User.Role.LEGAL}:
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
    if kind not in FieldMission.Kind.values:
        raise MissionError("اختر نوع المهمة.")
    if not details:
        raise MissionError("التفاصيل مطلوبة.")
    if not place_name:
        raise MissionError("اسم المحل مطلوب.")
    if not phone:
        raise MissionError("رقم الجوال مطلوب.")
    return kind, details, place_name, phone


def _assignees(user, payload):
    if user.role == User.Role.INSPECTOR:
        return user.governorate, user.region, [user]
    if user.role == User.Role.GOVERNOR:
        governorate = user.governorate
    else:
        raw = payload.get("governorate")
        if raw in (None, ""):
            raise MissionError("اختر المحافظة.")
        governorate = Governorate.objects.filter(pk=raw).first()
        if governorate is None:
            raise MissionError("اختر المحافظة.")
    active = User.objects.filter(role=User.Role.INSPECTOR, is_active=True, governorate=governorate)
    if (payload.get("scope") or "one") == "all":
        inspectors = list(active.order_by("pk"))
        if not inspectors:
            raise MissionError("لا يوجد مفتش مفعّل في هذه المحافظة.")
        return governorate, None, inspectors
    raw = payload.get("inspector")
    if raw in (None, ""):
        raise MissionError("اختر المفتش.")
    inspector = User.objects.filter(pk=raw).first()
    if inspector is None or inspector.role != User.Role.INSPECTOR:
        raise MissionError("اختر المفتش.")
    if not inspector.is_active:
        raise MissionError("المفتش غير مفعّل.")
    if inspector.governorate_id != governorate.pk:
        raise MissionError("المفتش لا يتبع هذه المحافظة.")
    return governorate, inspector.region, [inspector]


def open_mission(user, payload, image=None):
    if user.role not in {User.Role.ADMIN, User.Role.GOVERNOR, User.Role.INSPECTOR}:
        raise MissionError("هذا الدور لا يفتح مهمة ميدانية.", 403)
    if user.role != User.Role.ADMIN and not user.can_open_field_missions:
        raise MissionError("Forbidden", 403)
    kind, details, place_name, phone = _required(payload)
    if image:
        validate_upload(image, kinds={"image"})
    governorate, region, inspectors = _assignees(user, payload)
    with transaction.atomic():
        mission = FieldMission.objects.create(
            kind=kind,
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
    return mission
