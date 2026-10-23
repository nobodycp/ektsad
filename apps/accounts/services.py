import secrets
import string

from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError


def set_user_password(user, raw):
    if len(raw) < 12:
        raise ValidationError("كلمة المرور يجب أن تكون 12 محرفاً على الأقل.")
    user.set_password(raw)
    user.save(update_fields=["password"])


def reset_password(user):
    alphabet = string.ascii_letters + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(16))
    set_user_password(user, raw)
    return raw


def delete_user_sessions(user):
    for session in Session.objects.all():
        try:
            session_user_id = session.get_decoded().get("_auth_user_id")
        except Exception:
            continue
        if str(session_user_id) == str(user.pk):
            session.delete()
