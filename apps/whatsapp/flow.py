"""Citizen complaint steps on WhatsApp, using lists and reply buttons."""

import base64
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.complaints.models import Complaint
from apps.geography.models import Governorate, Region
from apps.publications.models import CrossingReport, PriceReport
from apps.telegram.citizen import (
    COMPLAINT_STEPS, FIXED_KINDS, KIND_LIMIT, KIND_PROMPT, KIND_TEXT_PROMPT, RESUME_PROMPT,
    WELCOME, confirmation, parse_point, receipt, stepped,
)
from apps.telegram.webhook import _accepted_image, notify_new_complaint
from apps.whatsapp.client import download_media, send_buttons, send_image_bytes, send_list, send_location_request, send_text
from apps.whatsapp.models import WhatsAppSession

MENU = (
    {"id": "nw", "title": "تقديم شكوى"},
    {"id": "pr", "title": "القائمة الاسترشادية"},
    {"id": "cr", "title": "حركة المعابر"},
)
LOCATION_TEXT = "أرسل موقع الشكوى إن رغبت.\nاضغط إرسال الموقع لموقع هاتفك الآن، أو اكتب تخطي."
RATE_LIMITED = "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً."
PAGE = 9


def handle_message(phone, message):
    kind = message.get("type")
    if kind == "interactive":
        reply = (message.get("interactive") or {})
        chosen = (reply.get("list_reply") or reply.get("button_reply") or {})
        _on_choice(phone, chosen.get("id") or "")
        return
    if kind == "location":
        point = message.get("location") or {}
        _on_location(phone, point.get("latitude"), point.get("longitude"))
        return
    if kind == "image":
        _on_image(phone, (message.get("image") or {}).get("id"))
        return
    if kind == "text":
        _on_text(phone, ((message.get("text") or {}).get("body") or "").strip())


def _session(phone):
    row, _created = WhatsAppSession.objects.get_or_create(phone=str(phone))
    return row


def _save(row, step, payload):
    row.step = step
    row.payload = payload
    row.save(update_fields=["step", "payload", "updated_at"])


def _menu(phone, welcome=False):
    row = _session(phone)
    _save(row, "", {})
    send_buttons(phone, WELCOME if welcome else "اختر من القائمة.", MENU)


def _show_kinds(phone):
    row = _session(phone)
    send_list(phone, stepped("kind", row.payload, KIND_PROMPT), [
        {"id": "k:price", "title": "غلاء أسعار"},
        {"id": "k:monopoly", "title": "احتكار"},
        {"id": "k:expiry", "title": "انتهاء صلاحية"},
        {"id": "k:other", "title": "أخرى"},
    ])


def _ask_kind_text(phone):
    row = _session(phone)
    send_text(phone, stepped("kind_text", row.payload, f"{KIND_TEXT_PROMPT}\nاكتب رجوع للعودة."))


def _show_places(phone, step, page):
    row = _session(phone)
    payload = dict(row.payload or {})
    if step == "region":
        items = list(Region.objects.filter(governorate_id=payload.get("governorate")).order_by("name"))
        prefix, more = "n:", f"np:{page + 1}"
    else:
        items = list(Governorate.objects.order_by("name"))
        prefix, more = "g:", f"gp:{page + 1}"
    if not items:
        send_text(phone, "لا توجد محافظات." if step == "governorate" else "لا توجد مناطق.")
        return
    start = max(page, 0) * PAGE
    chunk = items[start:start + PAGE]
    rows = [{"id": f"{prefix}{item.pk}", "title": item.name} for item in chunk]
    if start + PAGE < len(items):
        rows.append({"id": more, "title": "المزيد"})
    prompt = "اختر المحافظة." if step == "governorate" else "اختر المنطقة."
    send_list(phone, stepped(step, payload, prompt), rows)


def _ask_title(phone):
    row = _session(phone)
    send_text(phone, stepped("title", row.payload, "أرسل عنوان الشكوى.\nاكتب رجوع للعودة."))


def _ask_body(phone):
    row = _session(phone)
    send_text(phone, stepped("body", row.payload, "أرسل نص الشكوى.\nاكتب رجوع للعودة."))


def _ask_image(phone):
    row = _session(phone)
    send_text(phone, stepped("image", row.payload, "أرسل صورة أو اكتب تخطي.\nاكتب رجوع للعودة."))


def _ask_location(phone, saved=False):
    row = _session(phone)
    lead = "تم حفظ الصورة.\n" if saved else ""
    send_location_request(phone, stepped("location", row.payload, lead + LOCATION_TEXT))


def _show_confirm(phone):
    row = _session(phone)
    payload = dict(row.payload or {})
    governorate = Governorate.objects.filter(pk=payload.get("governorate")).first()
    region = Region.objects.filter(pk=payload.get("region")).first()
    send_buttons(
        phone,
        confirmation(payload, governorate.name if governorate else "", region.name if region else ""),
        [{"id": "ok", "title": "تقديم"}, {"id": "back", "title": "رجوع"}],
    )


def _start(phone):
    row = _session(phone)
    if row.step in COMPLAINT_STEPS:
        send_buttons(phone, RESUME_PROMPT, [
            {"id": "resume", "title": "تكمل"},
            {"id": "restart", "title": "أبدأ من جديد"},
        ])
        return
    _restart(phone)


def _restart(phone):
    row = _session(phone)
    _save(row, "kind", {})
    _show_kinds(phone)


def _resume(phone):
    row = _session(phone)
    step = row.step
    if step == "kind":
        _show_kinds(phone)
    elif step == "kind_text":
        _ask_kind_text(phone)
    elif step == "governorate":
        _show_places(phone, "governorate", 0)
    elif step == "region":
        _show_places(phone, "region", 0)
    elif step == "title":
        _ask_title(phone)
    elif step == "body":
        _ask_body(phone)
    elif step == "image":
        _ask_image(phone)
    elif step == "location":
        _ask_location(phone)
    elif step == "confirm":
        _show_confirm(phone)
    else:
        _restart(phone)


def _choose_kind(phone, data):
    row = _session(phone)
    payload = dict(row.payload or {})
    if data == "k:other":
        payload["kind_mode"] = "other"
        payload.pop("kind", None)
        _save(row, "kind_text", payload)
        _ask_kind_text(phone)
        return
    label = FIXED_KINDS.get(data)
    if not label:
        _show_kinds(phone)
        return
    payload["kind"] = label
    payload["kind_mode"] = "fixed"
    _save(row, "governorate", payload)
    _show_places(phone, "governorate", 0)


def _rewind(phone):
    row = _session(phone)
    payload = dict(row.payload or {})
    step = row.step
    if step == "kind_text":
        _save(row, "kind", payload)
        _show_kinds(phone)
    elif step == "governorate":
        if payload.get("kind_mode") == "other":
            _save(row, "kind_text", payload)
            _ask_kind_text(phone)
        else:
            _save(row, "kind", payload)
            _show_kinds(phone)
    elif step == "region":
        _save(row, "governorate", payload)
        _show_places(phone, "governorate", 0)
    elif step == "title":
        _save(row, "region", payload)
        _show_places(phone, "region", 0)
    elif step == "body":
        _save(row, "title", payload)
        _ask_title(phone)
    elif step == "image":
        _save(row, "body", payload)
        _ask_body(phone)
    elif step == "location":
        _save(row, "image", payload)
        _ask_image(phone)
    elif step == "confirm":
        _save(row, "location", payload)
        _ask_location(phone)
    else:
        _menu(phone)


def _on_choice(phone, data):
    if data in {"nw", "تقديم شكوى"}:
        _start(phone)
    elif data in {"pr", "القائمة الاسترشادية"}:
        _prices(phone)
    elif data in {"cr", "حركة المعابر"}:
        _crossings(phone)
    elif data == "resume":
        _resume(phone)
    elif data == "restart":
        _restart(phone)
    elif data in {"back", "رجوع"}:
        _rewind(phone)
    elif data == "ok":
        _finish(phone)
    elif data in FIXED_KINDS or data == "k:other":
        _choose_kind(phone, data)
    elif data.startswith("gp:"):
        _show_places(phone, "governorate", int(data.split(":")[1]))
    elif data.startswith("g:"):
        _pick_governorate(phone, data.split(":")[1])
    elif data.startswith("np:"):
        _show_places(phone, "region", int(data.split(":")[1]))
    elif data.startswith("n:"):
        _pick_region(phone, data.split(":")[1])
    else:
        _menu(phone, welcome=True)


def _on_text(phone, text):
    if text in {"تقديم شكوى", "nw"}:
        _start(phone)
        return
    if text in {"القائمة الاسترشادية", "قائمة الأسعار"}:
        _prices(phone)
        return
    if text == "حركة المعابر":
        _crossings(phone)
        return
    if text == "القائمة":
        _menu(phone)
        return
    if text == "رجوع":
        _rewind(phone)
        return
    row = _session(phone)
    if row.step == "kind_text":
        if not text or len(text) > KIND_LIMIT:
            _ask_kind_text(phone)
            return
        payload = dict(row.payload or {})
        payload["kind"] = text
        payload["kind_mode"] = "other"
        _save(row, "governorate", payload)
        _show_places(phone, "governorate", 0)
        return
    if row.step == "title":
        if not text:
            _ask_title(phone)
            return
        payload = dict(row.payload or {})
        payload["title"] = text
        _save(row, "body", payload)
        _ask_body(phone)
        return
    if row.step == "body":
        if not text:
            _ask_body(phone)
            return
        payload = dict(row.payload or {})
        payload["body"] = text
        _save(row, "image", payload)
        _ask_image(phone)
        return
    if row.step == "image" and text == "تخطي":
        _save(row, "location", dict(row.payload or {}))
        _ask_location(phone)
        return
    if row.step == "location" and text == "تخطي":
        payload = dict(row.payload or {})
        payload.pop("latitude", None)
        payload.pop("longitude", None)
        _save(row, "confirm", payload)
        _show_confirm(phone)
        return
    if row.step == "confirm" and text == "تقديم":
        _finish(phone)
        return
    if not row.step:
        _menu(phone, welcome=True)
        return
    send_text(phone, "اكتب رجوع للعودة، أو القائمة للبداية.")


def _pick_governorate(phone, raw):
    try:
        governorate = Governorate.objects.get(pk=int(raw))
    except (Governorate.DoesNotExist, TypeError, ValueError):
        send_text(phone, "المحافظة غير موجودة.")
        return
    row = _session(phone)
    payload = dict(row.payload or {})
    payload["governorate"] = governorate.pk
    payload.pop("region", None)
    _save(row, "region", payload)
    _show_places(phone, "region", 0)


def _pick_region(phone, raw):
    row = _session(phone)
    payload = dict(row.payload or {})
    try:
        region = Region.objects.get(pk=int(raw), governorate_id=payload.get("governorate"))
    except (Region.DoesNotExist, TypeError, ValueError):
        send_text(phone, "المنطقة غير موجودة.")
        return
    payload["region"] = region.pk
    _save(row, "title", payload)
    _ask_title(phone)


def _on_location(phone, latitude, longitude):
    row = _session(phone)
    if row.step != "location":
        send_text(phone, "الموقع يُرفق في خطوة الموقع.")
        return
    point = parse_point(latitude, longitude)
    if point is None:
        _ask_location(phone)
        return
    payload = dict(row.payload or {})
    payload["latitude"], payload["longitude"] = point
    _save(row, "confirm", payload)
    _show_confirm(phone)


def _on_image(phone, media_id):
    row = _session(phone)
    if row.step != "image" or not media_id:
        send_text(phone, "الصورة تُرفق بعد نص الشكوى.")
        return
    try:
        content, name = download_media(media_id)
    except Exception:
        _ask_image(phone)
        return
    if len(content) > 5 * 1024 * 1024:
        _ask_image(phone)
        return
    payload = dict(row.payload or {})
    payload["image"] = base64.b64encode(content).decode("ascii")
    payload["image_name"] = name
    _save(row, "location", payload)
    _ask_location(phone, saved=True)


def _finish(phone):
    row = _session(phone)
    payload = dict(row.payload or {})
    if payload.get("complaint_id"):
        send_buttons(phone, receipt(payload["complaint_id"]), MENU)
        _save(row, "", {})
        return
    if row.step != "confirm" or not payload.get("kind"):
        send_text(phone, "بيانات الشكوى غير مكتملة.")
        return
    since = timezone.now() - timedelta(hours=1)
    if Complaint.objects.filter(source="whatsapp", telegram_user_id=str(phone), created_at__gte=since).count() >= 10:
        send_text(phone, RATE_LIMITED)
        return
    try:
        region = Region.objects.select_related("governorate").get(
            pk=int(payload.get("region")), governorate_id=int(payload.get("governorate")),
        )
    except (Region.DoesNotExist, TypeError, ValueError):
        send_text(phone, "بيانات الشكوى غير مكتملة.")
        return
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    if not title or not body:
        send_text(phone, "بيانات الشكوى غير مكتملة.")
        return
    image = None
    if payload.get("image"):
        image = ContentFile(base64.b64decode(payload["image"]), name=payload.get("image_name") or "whatsapp.jpg")
        image = _accepted_image(image)
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    with transaction.atomic():
        complaint = Complaint.objects.create(
            governorate=region.governorate, region=region, title=title, body=body,
            kind=str(payload.get("kind"))[:40],
            latitude=Decimal(str(latitude)) if latitude is not None else None,
            longitude=Decimal(str(longitude)) if longitude is not None else None,
            source="whatsapp", telegram_chat_id=str(phone), telegram_user_id=str(phone), image=image,
        )
        notify_new_complaint(complaint)
    payload["complaint_id"] = complaint.pk
    _save(row, "confirm", payload)
    send_buttons(phone, receipt(complaint.pk), MENU)
    _save(row, "", {})


def _prices(phone):
    report = PriceReport.objects.order_by("-published_at").first()
    if report is None or not report.image:
        send_text(phone, "لا توجد قائمة أسعار منشورة.")
        return
    with report.image.open("rb") as image:
        send_image_bytes(phone, image.read(), "prices.jpg", "القائمة الاسترشادية")


def _crossings(phone):
    report = CrossingReport.objects.order_by("-published_at").first()
    if report is None or (not report.body and not report.image):
        send_text(phone, "لا توجد حركة معابر منشورة.")
        return
    if report.body:
        send_text(phone, report.body)
    if report.image:
        with report.image.open("rb") as image:
            send_image_bytes(phone, image.read(), "crossings.jpg")
