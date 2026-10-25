from datetime import timedelta
import json
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


def enqueue(chat_id, text="", photo="", markup=None):
    return _retry(lambda: TelegramOutbox.objects.create(chat_id=str(chat_id), text=text, photo=photo, markup=markup))


def next_delay(attempts):
    return (
        timedelta(seconds=30) if attempts <= 1 else
        timedelta(minutes=2) if attempts == 2 else
        timedelta(minutes=10) if attempts == 3 else
        timedelta(minutes=30)
    )


def _reply_markup(item):
    return item.markup


def _post(token, method, payload):
    response = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=10)
    response.raise_for_status()
    return response


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
            markup = _reply_markup(item)
            inline = isinstance(markup, dict) and "inline_keyboard" in markup
            if item.photo:
                from django.core.files.storage import default_storage

                data = {"chat_id": item.chat_id, "caption": item.text}
                if inline:
                    data["reply_markup"] = json.dumps({"remove_keyboard": True}, ensure_ascii=False)
                elif markup:
                    data["reply_markup"] = json.dumps(markup, ensure_ascii=False)
                with default_storage.open(item.photo, "rb") as photo:
                    response = httpx.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data=data,
                        files={"photo": photo},
                        timeout=10,
                    )
            else:
                payload = {"chat_id": item.chat_id, "text": item.text}
                if inline:
                    payload["reply_markup"] = {"remove_keyboard": True}
                elif markup:
                    payload["reply_markup"] = markup
                response = httpx.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json=payload,
                    timeout=10,
                )
            response.raise_for_status()
            if inline:
                _post(token, "editMessageReplyMarkup", {
                    "chat_id": item.chat_id,
                    "message_id": response.json()["result"]["message_id"],
                    "reply_markup": markup,
                })
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
