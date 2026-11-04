"""Effective permissions. The system admin has every permission. Other accounts take them from their role."""

from apps.accounts.models import User


ROLE_FIELDS = (
    "can_view_all_complaints",
    "can_view_reports",
    "can_manage_users",
    "can_manage_geography",
    "can_publish_prices",
    "can_publish_crossings",
    "can_view_field_missions",
    "can_open_field_missions",
    "can_manage_settings",
    "can_impersonate",
    "can_login_web",
)


def allows(user, name):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "role", None) == User.Role.ADMIN:
        return True
    if getattr(user, "role", None) == User.Role.INSPECTOR and name in {"can_view_field_missions", "can_open_field_missions"}:
        return True
    if getattr(user, "role", None) == User.Role.GOVERNOR and name == "can_view_field_missions":
        return True
    role = getattr(user, "staff_role", None)
    if role is not None:
        if name == "can_publish_prices":
            return bool(role.can_publish_prices)
        if name == "can_publish_crossings":
            return bool(role.can_publish_crossings)
        if name == "can_publish":
            return bool(role.can_publish_prices or role.can_publish_crossings)
        if name in {"can_open_field_missions", "can_view_field_missions"}:
            return bool(getattr(role, name, False))
        if name == "can_field_missions":
            return bool(role.can_view_field_missions or role.can_open_field_missions)
        return bool(getattr(role, name, False))
    if name in {"can_publish_prices", "can_publish_crossings", "can_view_all_complaints", "can_login_web", "can_open_field_missions", "can_view_field_missions"}:
        return bool(getattr(user, name, False))
    if name == "can_publish":
        return bool(getattr(user, "can_publish_prices", False) or getattr(user, "can_publish_crossings", False))
    if name == "can_field_missions":
        return bool(getattr(user, "can_view_field_missions", False) or getattr(user, "can_open_field_missions", False))
    return False


def spans_governorates(user):
    """مدير المحافظات sees every governorate, one at a time."""
    return getattr(user, "role", None) == User.Role.CUSTOM and allows(user, "can_view_all_complaints")
