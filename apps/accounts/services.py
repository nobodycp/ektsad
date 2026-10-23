from django.core.exceptions import ValidationError


def set_user_password(user, raw):
    if len(raw) < 12:
        raise ValidationError("كلمة المرور يجب أن تكون 12 محرفاً على الأقل.")
    user.set_password(raw)
    user.save(update_fields=["password"])
