import base64
import os
from datetime import timedelta

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.complaints.models import Complaint
from apps.complaints.services import (
    accept_complaint, assign_complaint, close_legal, submit_field_report, visible_complaints,
)
from apps.geography.models import Governorate, Region
from apps.publications.models import CrossingReport, PriceReport
from apps.telegram.links import consume_staff_link
from apps.telegram.models import (
    TelegramDraft, TelegramLink, TelegramOutbox, TelegramUpdate, TelegramWebhookStatus,
)
from apps.telegram.outbox import enqueue


UNLINKED = "هذا الحساب غير مربوط. اطلب رابط الربط من مدير النظام."
RECEIVED = "تم استلام الشكوى."
RATE_LIMITED = "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً."


def _value(name):
    return getattr(settings, name, "") or os.environ.get(name, "")


def _retry(operation):
    for attempt in range(3):
        try:
            return operation()
        except OperationalError:
            if attempt == 2:
                raise


def record_update(update_id):
    try:
        with transaction.atomic():
            _retry(lambda: TelegramUpdate.objects.create(update_id=update_id))
        return True
    except IntegrityError:
        return False


def _status_update(**values):
    status = TelegramWebhookStatus.current()
    for key, value in values.items():
        setattr(status, key, value)
    status.save()


def register_webhook():
    """Attempt webhook registration; deployment must remain usable on failure."""
    _status_update(last_attempt_at=timezone.now())
    token, secret, base = _value("TELEGRAM_BOT_TOKEN"), _value("TELEGRAM_WEBHOOK_SECRET"), _value("PUBLIC_BASE_URL")
    if not token or not secret or not base:
        _status_update(registered=False, last_error="إعدادات الويب هوك غير مكتملة.")
        return False
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": f"{base.rstrip('/')}/api/telegram/webhook/", "secret_token": secret},
            timeout=10,
        )
        response.raise_for_status()
    except Exception as error:
        _status_update(registered=False, last_error=str(error))
        return False
    _status_update(registered=True, last_error="")
    return True


def _linked_user(telegram_id):
    link = TelegramLink.objects.select_related("user").filter(telegram_id=str(telegram_id)).first()
    return link.user if link and link.user.is_active else None


def notify_new_complaint(complaint):
    inspectors = User.objects.filter(
        is_active=True, role=User.Role.INSPECTOR, region_id=complaint.region_id,
        telegram_link__isnull=False,
    ).select_related("telegram_link")
    governors = User.objects.filter(
        is_active=True, role=User.Role.GOVERNOR, governorate_id=complaint.governorate_id,
        telegram_link__isnull=False,
    ).select_related("telegram_link")
    message = f"وصلت شكوى في {complaint.region.name} بعنوان {complaint.title}."
    for user in list(inspectors) + list(governors):
        enqueue(user.telegram_link.telegram_id, message)


def _create_complaint(chat_id, user_id, governorate_id, region_id, title, body, image=None):
    region = Region.objects.select_related("governorate").filter(pk=region_id, governorate_id=governorate_id).first()
    if region is None or not title.strip() or not body.strip():
        return None
    since = timezone.now() - timedelta(hours=1)
    if Complaint.objects.filter(
        source=Complaint.Source.TELEGRAM, telegram_user_id=str(user_id), created_at__gte=since
    ).count() >= 10:
        enqueue(chat_id, RATE_LIMITED)
        return False
    with transaction.atomic():
        complaint = Complaint.objects.create(
            governorate=region.governorate, region=region, title=title.strip(), body=body.strip(),
            source=Complaint.Source.TELEGRAM, telegram_chat_id=str(chat_id), telegram_user_id=str(user_id), image=image,
        )
        notify_new_complaint(complaint)
        enqueue(chat_id, RECEIVED)
    return complaint


def _publications(chat_id, text):
    if text in {"قائمة الأسعار", "prices", "/prices"}:
        report = PriceReport.objects.order_by("-published_at").first()
        if report is None or not report.image:
            enqueue(chat_id, "لا توجد قائمة أسعار منشورة.")
        else:
            enqueue(chat_id, photo=report.image.name)
        return True
    if text in {"حركة المعابر", "crossings", "/crossings"}:
        report = CrossingReport.objects.order_by("-published_at").first()
        if report is None or (not report.body and not report.image):
            enqueue(chat_id, "لا توجد حركة معابر منشورة.")
        else:
            if report.body:
                enqueue(chat_id, report.body)
            if report.image:
                enqueue(chat_id, photo=report.image.name)
        return True
    return False


def _staff_action(chat_id, telegram_id, text):
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED)
        return True
    bits = text.split(maxsplit=3)
    command = bits[0]
    try:
        complaint = Complaint.objects.get(pk=int(bits[1]))
        if command == "/accept":
            accept_complaint(complaint, user, channel="telegram", ip=None, telegram_id=str(telegram_id))
            governors = User.objects.filter(
                role=User.Role.GOVERNOR, is_active=True, governorate_id=complaint.governorate_id,
                telegram_link__isnull=False,
            ).select_related("telegram_link")
            for governor in governors:
                enqueue(governor.telegram_link.telegram_id, f"قبل المفتش {user.display_name or user.username} الشكوى وتوجه للمتابعة الميدانية.")
        elif command == "/assign":
            inspector = User.objects.get(pk=int(bits[2]))
            assign_complaint(complaint, user, inspector, channel="telegram", ip=None, telegram_id=str(telegram_id))
        elif command == "/field":
            destination, body = bits[2], bits[3]
            submit_field_report(
                complaint, user, body, [], destination,
                channel="telegram", ip=None, telegram_id=str(telegram_id),
            )
            if destination == "governor":
                _citizen_resolution(complaint)
        elif command == "/close":
            close_legal(complaint, user, bits[2] if len(bits) > 2 else "", channel="telegram", ip=None, telegram_id=str(telegram_id))
            _citizen_resolution(complaint)
        else:
            return False
    except (Complaint.DoesNotExist, User.DoesNotExist, IndexError, ValueError, ValidationError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        enqueue(chat_id, message)
        return True
    enqueue(chat_id, "تم التنفيذ.")
    return True


def _citizen_resolution(complaint):
    if complaint.source == Complaint.Source.TELEGRAM and complaint.telegram_chat_id:
        enqueue(complaint.telegram_chat_id, f"تم التعامل مع الشكوى تبعك: {complaint.title}.")


def _work_list(chat_id, telegram_id, text):
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED)
        return
    queryset = visible_complaints(user)
    if text == "وصلت":
        queryset = queryset.filter(status=Complaint.Status.RECEIVED)
    elif text == "معلقة":
        queryset = queryset.filter(status__in=[Complaint.Status.FIELD, Complaint.Status.LEGAL])
    elif text == "مغلقة":
        queryset = queryset.filter(status__in=[Complaint.Status.FINISHED, Complaint.Status.RESOLVED])
    rows = list(queryset.order_by("-created_at")[:20])
    if not rows:
        enqueue(chat_id, "لا توجد شكاوى.")
        return
    enqueue(chat_id, "\n".join(f"{item.pk}. {item.title} — {item.status}" for item in rows))


def _image_file(draft):
    if not draft or not draft.payload.get("image"):
        return None
    return ContentFile(base64.b64decode(draft.payload["image"]), name=draft.payload["image_name"])


def _finish_draft(chat_id, user_id, draft):
    payload = draft.payload
    result = _create_complaint(
        chat_id, user_id, payload.get("governorate"), payload.get("region"),
        payload.get("title", ""), payload.get("body", ""), _image_file(draft),
    )
    if result:
        draft.delete()
    elif result is None:
        enqueue(chat_id, "بيانات الشكوى غير مكتملة.")


def _advance_draft(chat_id, user_id, text):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or draft.step not in {"governorate", "region", "title", "body", "image"}:
        return False
    cleaned = text.strip()
    payload = dict(draft.payload)
    if draft.step == "governorate":
        governorate = Governorate.objects.filter(name=cleaned).first()
        if governorate is None:
            enqueue(chat_id, "المحافظة غير موجودة.")
            return True
        payload["governorate"] = governorate.pk
        draft.step = "region"
        reply = "أرسل اسم المنطقة."
    elif draft.step == "region":
        region = Region.objects.filter(governorate_id=payload.get("governorate"), name=cleaned).first()
        if region is None:
            enqueue(chat_id, "المنطقة غير موجودة.")
            return True
        payload["region"] = region.pk
        draft.step = "title"
        reply = "أرسل عنوان الشكوى."
    elif draft.step == "title":
        payload["title"] = cleaned
        draft.step = "body"
        reply = "أرسل نص الشكوى."
    elif draft.step == "body":
        payload["body"] = cleaned
        draft.step = "image"
        reply = "أرسل صورة أو اكتب تخطي."
    else:
        if cleaned not in {"تخطي", "تقديم الشكوى"}:
            enqueue(chat_id, "أرسل صورة أو اكتب تخطي.")
            return True
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _finish_draft(chat_id, user_id, draft)
        return True
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    enqueue(chat_id, reply)
    return True


def _start_complaint(chat_id):
    draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "governorate", "payload": {}})
    if draft.step != "governorate":
        draft.step = "governorate"
        draft.save(update_fields=["step", "updated_at"])
    enqueue(chat_id, "أرسل المحافظة ثم المنطقة ثم العنوان ثم نص الشكوى.")


def _handle_complaint_command(chat_id, user_id, text):
    parts = text.split(maxsplit=4)
    if len(parts) < 5:
        _start_complaint(chat_id)
        return
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    image = (
        ContentFile(base64.b64decode(draft.payload["image"]), name=draft.payload["image_name"])
        if draft and draft.payload.get("image") else None
    )
    result = _create_complaint(chat_id, user_id, parts[1], parts[2], parts[3], parts[4], image)
    if result:
        TelegramDraft.objects.filter(chat_id=str(chat_id)).delete()
    elif result is None:
        _start_complaint(chat_id)


def _download_photo(photo):
    token = _value("TELEGRAM_BOT_TOKEN")
    if not token or not photo:
        return None
    file_id = photo[-1].get("file_id")
    if not file_id:
        return None
    response = httpx.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=10)
    response.raise_for_status()
    file_path = response.json()["result"]["file_path"]
    content = httpx.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=10)
    content.raise_for_status()
    return {
        "image": base64.b64encode(content.content).decode("ascii"),
        "image_name": file_path.rsplit("/", 1)[-1],
    }


def handle_update(update):
    message = update.get("message") or update.get("callback_query", {}).get("message") or {}
    callback = update.get("callback_query") or {}
    chat_id = (message.get("chat") or {}).get("id")
    sender = (update.get("message") or callback.get("from") or {}).get("from") or (update.get("message") or {}).get("from") or {}
    user_id = sender.get("id")
    text = (update.get("message") or {}).get("text") or callback.get("data") or ""
    if chat_id is None:
        return
    photo = (update.get("message") or {}).get("photo")
    if photo:
        try:
            downloaded = _download_photo(photo)
        except Exception:
            downloaded = None
        if downloaded:
            draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "image"})
            draft.payload = {**draft.payload, **downloaded}
            draft.save(update_fields=["payload", "updated_at"])
    if text.startswith("/start "):
        if consume_staff_link(text.split(maxsplit=1)[1], user_id):
            user = _linked_user(user_id)
            enqueue(chat_id, f"تم ربط الحساب: {user.display_name or user.username}.")
        else:
            enqueue(chat_id, "رابط الربط غير صالح أو منتهي.")
    elif text.startswith("/complaint"):
        _handle_complaint_command(chat_id, user_id, text)
    elif _publications(chat_id, text):
        return
    elif text.startswith(("/accept", "/assign", "/field", "/close")):
        _staff_action(chat_id, user_id, text)
    elif text in {"شكاوى", "وصلت", "معلقة", "مغلقة"}:
        _work_list(chat_id, user_id, text)
    elif text == "تقديم شكوى":
        _start_complaint(chat_id)
    elif text and _advance_draft(chat_id, user_id, text):
        return
    elif text:
        enqueue(chat_id, "تقديم شكوى، قائمة الأسعار، أو حركة المعابر.")
    elif photo:
        enqueue(chat_id, "تم حفظ الصورة. اكتب تقديم الشكوى أو تخطي.")
