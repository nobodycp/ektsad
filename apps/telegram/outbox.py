from datetime import timedelta
import os

import httpx
from django.db import OperationalError
from django.utils import timezone

from apps.telegram.models import TelegramOutbox


def _retry(operation):
    for attempt in range(3):
        try:
            return operation()
        except OperationalError:
            if attempt == 2:
                raise


def enqueue(chat_id, text):
    return _retry(lambda: TelegramOutbox.objects.create(chat_id=str(chat_id), text=text))


def next_delay(attempts):
    return (
        timedelta(seconds=30) if attempts <= 1 else
        timedelta(minutes=2) if attempts == 2 else
        timedelta(minutes=10) if attempts == 3 else
        timedelta(minutes=30)
    )


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
            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": item.chat_id, "text": item.text},
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
