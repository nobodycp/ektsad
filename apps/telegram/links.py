import hashlib
import os
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.telegram.models import TelegramLink, TelegramLinkToken


NOT_CONFIGURED = "البوت غير مهيأ."


def _value(name):
    return getattr(settings, name, "") or os.environ.get(name, "")


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_staff_link(user):
    token_value = _value("TELEGRAM_BOT_TOKEN")
    username = _value("TELEGRAM_BOT_USERNAME")
    if not token_value or not username:
        raise ValueError(NOT_CONFIGURED)
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        TelegramLinkToken.objects.create(
            user=user, token_hash=_digest(raw), expires_at=timezone.now() + timedelta(hours=24)
        )
    return f"https://t.me/{username}?start={raw}"


def consume_staff_link(raw, telegram_id):
    with transaction.atomic():
        token = TelegramLinkToken.objects.select_for_update().filter(
            token_hash=_digest(raw), used_at__isnull=True, expires_at__gt=timezone.now()
        ).select_related("user").first()
        if token is None or not token.user.is_active:
            return False
        if TelegramLink.objects.filter(telegram_id=str(telegram_id)).exists():
            return False
        if hasattr(token.user, "telegram_link"):
            return False
        TelegramLink.objects.create(user=token.user, telegram_id=str(telegram_id))
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
    return True
