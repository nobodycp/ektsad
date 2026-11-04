from django.core.exceptions import ValidationError

from apps.accounts.models import StaffRole, User
from apps.geography.models import Governorate, Region


PREVIEW_ROLES = {
    "director": ("مدير المحافظات", User.Role.CUSTOM),
    "governor": ("مدير المحافظة", User.Role.GOVERNOR),
    "inspector": ("مفتش", User.Role.INSPECTOR),
    "legal": ("الشؤون القانونية", User.Role.LEGAL),
    "clerk": ("إداري المحافظة", User.Role.CUSTOM),
}


def apply_preview_role(user, key, governorate_id=None, region_id=None):
    if not getattr(user, "is_preview", False):
        raise ValidationError("غير مسموح.")
    chosen = PREVIEW_ROLES.get(key)
    if chosen is None:
        raise ValidationError("صلاحية غير معروفة.")
    name, role = chosen
    staff_role = StaffRole.objects.filter(name=name).first()
    if staff_role is None:
        raise ValidationError("الدور غير موجود.")
    governorate = None
    region = None
    if key in {"governor", "clerk", "inspector"}:
        governorate = Governorate.objects.filter(pk=governorate_id).first()
        if governorate is None:
            raise ValidationError("اختر المحافظة.")
    if key == "inspector":
        region = Region.objects.filter(pk=region_id, governorate=governorate).first()
        if region is None:
            raise ValidationError("اختر المنطقة.")
    user.role = role
    user.staff_role = staff_role
    user.governorate = governorate
    user.region = region
    user.save(update_fields=["role", "staff_role", "governorate", "region"])
    return user
