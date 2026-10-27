from datetime import timedelta

from django.utils import timezone

from apps.telegram.models import TelegramLink

ONLINE_FOR = timedelta(minutes=5)


def touch(telegram_id, username):
    if not telegram_id:
        return
    link = TelegramLink.objects.filter(telegram_id=str(telegram_id)).first()
    if link is None:
        return
    link.last_seen_at = timezone.now()
    fields = ["last_seen_at"]
    handle = str(username or "").strip().lstrip("@")[:32]
    if handle and handle != link.telegram_username:
        link.telegram_username = handle
        fields.append("telegram_username")
    link.save(update_fields=fields)


def is_online(link):
    return bool(link.last_seen_at and timezone.now() - link.last_seen_at <= ONLINE_FOR)


def snapshot(user):
    try:
        link = user.telegram_link
    except TelegramLink.DoesNotExist:
        link = None
    if link is None:
        return {"telegram_linked": False, "telegram_username": "", "telegram_online": False}
    return {
        "telegram_linked": True,
        "telegram_username": link.telegram_username,
        "telegram_online": is_online(link),
    }


def button_label(user):
    name = user.display_name or user.username
    state = "مفعّل" if user.is_active else "موقوف"
    try:
        link = user.telegram_link
    except TelegramLink.DoesNotExist:
        link = None
    if link is None:
        return f"{name} · {state}"[:64]
    handle = f"@{link.telegram_username}" if link.telegram_username else "بدون يوزر"
    presence = "متصل" if is_online(link) else "غير متصل"
    prefix = f"{name} ✈ {handle} · {presence}"
    room = 64 - len(f" · {state}")
    if len(prefix) > room:
        prefix = prefix[: max(room - 1, 0)].rstrip() + "…"
    return f"{prefix} · {state}"
