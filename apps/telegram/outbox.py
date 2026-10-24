from datetime import timedelta
import json
import os

import httpx
from django.db import OperationalError
from django.utils import timezone

from apps.telegram.models import TelegramLink, TelegramOutbox


def _retry(operation):
    for attempt in range(3):
        try:
            return operation()
        except OperationalError:
            if attempt == 2:
                raise


def enqueue(chat_id, text="", photo="", markup=None):
    return _retry(lambda: TelegramOutbox.objects.create(chat_id=str(chat_id), text=text, photo=photo, markup=markup))


def next_delay(attempts):
    return (
        timedelta(seconds=30) if attempts <= 1 else
        timedelta(minutes=2) if attempts == 2 else
        timedelta(minutes=10) if attempts == 3 else
        timedelta(minutes=30)
    )


def keyboard_for(chat_id):
    rows = [
        [{"text": "تقديم شكوى"}, {"text": "قائمة الأسعار"}],
        [{"text": "حركة المعابر"}],
    ]
    link = TelegramLink.objects.select_related("user").filter(telegram_id=str(chat_id)).first()
    if link and link.user.is_active:
        rows.append([{"text": "شكاوى"}])
        if link.user.role == "governor":
            rows.append([{"text": "وصلت"}, {"text": "معلقة"}, {"text": "مغلقة"}])
    return {"keyboard": rows, "resize_keyboard": True}


def _reply_markup(item):
    if item.markup:
        return item.markup
    return keyboard_for(item.chat_id)


def send_telegram_outbox():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return 0
    due = TelegramOutbox.objects.filter(
        status=TelegramOutbox.Status.PENDING, next_attempt_at__lte=timezone.now()
    ).order_by("pk")
    sent = 0
    for item in due:
        try:
            if item.photo:
                from django.core.files.storage import default_storage

                with default_storage.open(item.photo, "rb") as photo:
                    response = httpx.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={
                            "chat_id": item.chat_id,
                            "caption": item.text,
                            "reply_markup": json.dumps(_reply_markup(item), ensure_ascii=False),
                        },
                        files={"photo": photo},
                        timeout=10,
                    )
            else:
                response = httpx.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": item.chat_id,
                        "text": item.text,
                        "reply_markup": _reply_markup(item),
                    },
                    timeout=10,
                )
            response.raise_for_status()
        except Exception as error:
            item.attempts += 1
            item.last_error = str(error)
            item.next_attempt_at = timezone.now() + next_delay(item.attempts)
            _retry(item.save)
            continue
        item.status = TelegramOutbox.Status.SENT
        item.sent_at = timezone.now()
        item.last_error = ""
        _retry(item.save)
        sent += 1
    return sent
