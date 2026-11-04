import base64
import json
import os
from datetime import timedelta
from decimal import Decimal

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.complaints.models import Complaint
from apps.complaints.services import (
    accept_complaint, assign_complaint, close_legal, return_complaint, submit_field_report, visible_complaints,
)
from apps.geography.models import Governorate, Region
from apps.publications.models import CrossingReport, PriceReport
from apps.telegram.links import consume_staff_link
from apps.telegram.models import (
    TelegramDraft, TelegramLink, TelegramOutbox, TelegramUpdate, TelegramWebhookStatus,
)
from apps.telegram.citizen import (
    COMPLAINT_STEPS, FIXED_KINDS, KIND_LIMIT, KIND_PROMPT, KIND_TEXT_PROMPT, LOCATION_PROMPT,
    RESUME_PROMPT, WELCOME, confirmation, kind_rows, location_rows, map_link, map_page_url,
    parse_point, receipt, resume_rows, stepped,
)
from apps.telegram.keyboard import attach_keyboard
from apps.telegram.outbox import enqueue as _enqueue


def enqueue(chat_id, text="", photo="", markup=None):
    """Queue the message. The outbox worker delivers it, so this request returns at once."""
    if markup:
        markup = attach_keyboard(chat_id, markup)
    return _enqueue(chat_id, text, photo=photo, markup=markup)


UNLINKED = "هذا الحساب غير مربوط. اطلب رابط الربط من مدير النظام."
RECEIVED = "تم استلام الشكوى."
RATE_LIMITED = "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً."
PAGE_SIZE = 6
COMPLAINT_PAGE = 15


def _home_markup():
    return {"inline_keyboard": [[{"text": "القائمة", "callback_data": "mn"}]]}


def _menu_markup(chat_id):
    from apps.telegram.buttons import rows_for

    link = TelegramLink.objects.select_related("user__staff_role").filter(telegram_id=str(chat_id)).first()
    user = link.user if link and link.user.is_active else None
    return {"inline_keyboard": rows_for(user)}


def _clear_field_draft(chat_id):
    TelegramDraft.objects.filter(chat_id=str(chat_id), step__in=["field_text", "field_dest"]).delete()


def _show_menu(chat_id, welcome=False):
    from apps.telegram.keyboard import reset_place

    _clear_field_draft(chat_id)
    TelegramDraft.objects.filter(chat_id=str(chat_id)).update(step="")
    reset_place(chat_id)
    user = _linked_user(chat_id)
    if welcome and user is None:
        text = WELCOME
    elif user is not None:
        text = _identity_line(user)
    else:
        text = "اختر من القائمة."
    enqueue(chat_id, text, markup=_menu_markup(chat_id))


def _draft_for(chat_id):
    return TelegramDraft.objects.filter(chat_id=str(chat_id)).first()


def _step_text(chat_id, step, body):
    draft = _draft_for(chat_id)
    return stepped(step, draft.payload if draft else {}, body)


def _paged(items, page, text_of, data_of, page_prefix, page_size=PAGE_SIZE):
    page = max(int(page), 0)
    start = page * page_size
    rows = [[
        {"text": text_of(item)[:40], "callback_data": data_of(item)},
    ] for item in items[start:start + page_size]]
    nav = []
    if start:
        nav.append({"text": "السابق", "callback_data": f"{page_prefix}:{page - 1}"})
    if start + page_size < len(items):
        nav.append({"text": "التالي", "callback_data": f"{page_prefix}:{page + 1}"})
    if nav:
        rows.append(nav)
    return rows


def _show_governorates(chat_id, page):
    items = list(Governorate.objects.order_by("name"))
    if not items:
        enqueue(chat_id, "لا توجد محافظات.", markup=_home_markup())
        return
    rows = _paged(items, page, lambda item: item.name, lambda item: f"g:{item.pk}", "gp")
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    enqueue(chat_id, _step_text(chat_id, "governorate", "اختر المحافظة."), markup={"inline_keyboard": rows})


def _show_regions(chat_id, page):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    governorate_id = (draft.payload or {}).get("governorate") if draft else None
    items = list(Region.objects.filter(governorate_id=governorate_id).order_by("name"))
    if not items:
        enqueue(chat_id, "لا توجد مناطق.", markup=_home_markup())
        return
    rows = _paged(items, page, lambda item: item.name, lambda item: f"n:{item.pk}", "np")
    rows.append([
        {"text": "رجوع", "callback_data": "gp:0"},
        {"text": "القائمة", "callback_data": "mn"},
    ])
    enqueue(chat_id, _step_text(chat_id, "region", "اختر المنطقة."), markup={"inline_keyboard": rows})


def _image_markup():
    return {"inline_keyboard": [
        [{"text": "تخطي", "callback_data": "sk"}],
        [{"text": "القائمة", "callback_data": "mn"}],
    ]}


def _ask_image(chat_id, saved=False):
    body = "تم حفظ الصورة." if saved else "أرسل صورة أو اضغط تخطي."
    enqueue(chat_id, _step_text(chat_id, "image", body), markup=_image_markup())


def _ask_title(chat_id):
    enqueue(chat_id, _step_text(chat_id, "title", "أرسل عنوان الشكوى."), markup=_home_markup())


def _ask_body(chat_id):
    enqueue(chat_id, _step_text(chat_id, "body", "أرسل نص الشكوى."), markup=_home_markup())


def _ask_kind_text(chat_id):
    enqueue(chat_id, _step_text(chat_id, "kind_text", KIND_TEXT_PROMPT), markup=_home_markup())


def _show_kinds(chat_id):
    enqueue(chat_id, _step_text(chat_id, "kind", KIND_PROMPT), markup={"inline_keyboard": kind_rows()})


def _ask_location(chat_id, saved=False):
    body = f"تم حفظ الصورة.\n{LOCATION_PROMPT}" if saved else LOCATION_PROMPT
    enqueue(
        chat_id,
        _step_text(chat_id, "location", body),
        markup={"inline_keyboard": location_rows(map_page_url(_value("PUBLIC_BASE_URL")))},
    )


def _show_confirm(chat_id):
    draft = _draft_for(chat_id)
    payload = dict(draft.payload) if draft else {}
    governorate = Governorate.objects.filter(pk=payload.get("governorate")).first()
    region = Region.objects.filter(pk=payload.get("region")).first()
    enqueue(
        chat_id,
        confirmation(payload, governorate.name if governorate else "", region.name if region else ""),
        markup={"inline_keyboard": [[{"text": "تقديم", "callback_data": "ok"}]]},
    )


def _value(name):
    stored = _stored_setting(name)
    if stored:
        return stored
    return getattr(settings, name, "") or os.environ.get(name, "")


def _stored_setting(name):
    from apps.common.models import SystemSettings

    row = SystemSettings.objects.filter(pk=1).first()
    if row is None:
        return ""
    return {
        "TELEGRAM_BOT_TOKEN": row.telegram_bot_token,
        "TELEGRAM_BOT_USERNAME": row.telegram_bot_username,
        "TELEGRAM_WEBHOOK_SECRET": row.telegram_webhook_secret,
    }.get(name, "")


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
    link = TelegramLink.objects.select_related("user__staff_role").filter(telegram_id=str(telegram_id)).first()
    return link.user if link and link.user.is_active else None


def _identity_line(user):
    name = (user.display_name or user.username or "").strip()
    role = getattr(user, "staff_role", None)
    title = role.name if role is not None and role.name else ROLE_LABELS.get(user.role, "")
    return f"{name} — {title}" if title else name


def _linked_staff(role, **filters):
    return User.objects.filter(
        is_active=True, role=role, telegram_link__isnull=False, **filters,
    ).select_related("telegram_link")


def _clip(text, limit=3500):
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _detail_block(complaint, body):
    lines = []
    if complaint.kind:
        lines.append(f"النوع: {complaint.kind}")
    lines.extend([
        f"المحافظة: {complaint.governorate.name}",
        f"المنطقة: {complaint.region.name}",
        f"العنوان: {complaint.title}",
        f"المحتوى: {body}",
    ])
    if complaint.latitude is not None and complaint.longitude is not None:
        lines.append(f"الموقع: {map_link(complaint.latitude, complaint.longitude)}")
    return "\n".join(lines)


def notify_new_complaint(complaint):
    details = _detail_block(complaint, _clip(complaint.body))
    accept = {"inline_keyboard": [[
        {"text": "قبول", "callback_data": f"/accept {complaint.pk}"},
        {"text": "رفض وإرجاع للمدير", "callback_data": f"rj:{complaint.pk}"},
    ]]}
    opened = {"inline_keyboard": [[{"text": "فتح", "callback_data": f"op:{complaint.pk}"}]]}
    for user in _linked_staff(User.Role.INSPECTOR, region_id=complaint.region_id):
        enqueue(user.telegram_link.telegram_id, f"لديك شكوى جديدة.\n{details}", markup=accept)
    for user in _linked_staff(User.Role.GOVERNOR, governorate_id=complaint.governorate_id):
        enqueue(user.telegram_link.telegram_id, f"وصلت شكوى.\n{details}", markup=opened)


def notify_legal_complaint(complaint):
    message = "لديك شكوى جديدة.\n" + _detail_block(complaint, _clip(complaint.body))
    opened = {"inline_keyboard": [[{"text": "فتح", "callback_data": f"op:{complaint.pk}"}]]}
    for user in _linked_staff(User.Role.LEGAL):
        enqueue(user.telegram_link.telegram_id, message, markup=opened)


def notify_new_mission(mission, *, governors=True):
    from apps.accounts.permissions import allows

    details = (
        f"النوع: {mission.kind}\n"
        f"الأولوية: {mission.priority}\n"
        f"المحل: {mission.place_name}\n"
        f"التفاصيل: {_clip(mission.details)}"
    )
    opened = {"inline_keyboard": [[{"text": "فتح", "callback_data": f"mo:{mission.pk}"}]]}
    inspector_ids = set(mission.assignees.filter(
        user__is_active=True, user__role=User.Role.INSPECTOR, user__telegram_link__isnull=False,
    ).values_list("user_id", flat=True))
    if mission.region_id:
        inspector_ids.update(
            _linked_staff(User.Role.INSPECTOR, region_id=mission.region_id).values_list("pk", flat=True)
        )
    for user in User.objects.filter(pk__in=inspector_ids).select_related("telegram_link"):
        enqueue(user.telegram_link.telegram_id, f"لديك مهمة جديدة.\n{details}", markup=opened)
    if not governors:
        return
    for governor in _linked_staff(User.Role.GOVERNOR, governorate_id=mission.governorate_id):
        if allows(governor, "can_view_field_missions"):
            enqueue(governor.telegram_link.telegram_id, f"وصلت مهمة.\n{details}", markup=opened)


def notify_complaint_reply(complaint):
    from apps.complaints.models import FollowUp

    finding = (
        complaint.follow_ups.filter(place=FollowUp.Place.FIELD)
        .order_by("-pk")
        .values_list("body", flat=True)
        .first()
    ) or ""
    message = (
        f"رد المفتش على الشكوى: {complaint.title}\n"
        f"المفتش: {complaint.inspector_name or 'المفتش'}\n"
        f"الرد: {_note(finding)}\n"
        f"الحالة: {complaint.status}"
    )
    markup = {"inline_keyboard": [
        [{"text": "إغلاق وإنهاء الشكوى", "callback_data": f"gc:{complaint.pk}"}],
        [{"text": "إحالة للشؤون القانونية", "callback_data": f"gl:{complaint.pk}"}],
        [{"text": "فتح", "callback_data": f"op:{complaint.pk}"}],
    ]}
    for governor in _linked_staff(User.Role.GOVERNOR, governorate_id=complaint.governorate_id):
        enqueue(governor.telegram_link.telegram_id, message, markup=markup)


def notify_complaint_decision(complaint, decision):
    link = TelegramLink.objects.filter(user_id=complaint.inspector_id).first()
    if link is None:
        return
    verb = (
        "أنهى مدير المحافظة الشكوى."
        if decision == "close"
        else "أحال مدير المحافظة الشكوى إلى الشؤون القانونية."
    )
    enqueue(
        link.telegram_id,
        f"{verb}\n{complaint.title}",
        markup={"inline_keyboard": [[{"text": "فتح", "callback_data": f"op:{complaint.pk}"}]]},
    )


def notify_mission_reply(mission):
    finding = (
        mission.follow_ups.filter(place="field").order_by("-pk").values_list("body", flat=True).first()
    ) or ""
    names = [name for name in mission.assignees.values_list("display_name", flat=True) if name]
    message = (
        f"رد على المهمة: {mission.place_name}\n"
        f"أنشأها: {mission.created_by_name or '—'}\n"
        f"المفتش: {'، '.join(names) or '—'}\n"
        f"الرد: {_note(finding)}\n"
        f"الحالة: {mission.status}"
    )
    opened = {"inline_keyboard": [[{"text": "فتح", "callback_data": f"mo:{mission.pk}"}]]}
    for governor in _linked_staff(User.Role.GOVERNOR, governorate_id=mission.governorate_id):
        enqueue(governor.telegram_link.telegram_id, message, markup=opened)


def notify_legal_mission(mission):
    message = (
        "لديك مهمة جديدة.\n"
        f"النوع: {mission.kind}\n"
        f"الأولوية: {mission.priority}\n"
        f"المحل: {mission.place_name}\n"
        f"التفاصيل: {_clip(mission.details)}"
    )
    opened = {"inline_keyboard": [[{"text": "فتح", "callback_data": f"mo:{mission.pk}"}]]}
    for user in _linked_staff(User.Role.LEGAL):
        enqueue(user.telegram_link.telegram_id, message, markup=opened)


def _create_complaint(chat_id, user_id, governorate_id, region_id, title, body, image=None, kind="", latitude=None, longitude=None):
    try:
        region = Region.objects.select_related("governorate").filter(
            pk=int(region_id), governorate_id=int(governorate_id)
        ).first()
    except (TypeError, ValueError):
        return None
    if region is None or not str(title).strip() or not str(body).strip():
        return None
    image = _accepted_image(image)
    since = timezone.now() - timedelta(hours=1)
    if Complaint.objects.filter(
        source=Complaint.Source.TELEGRAM, telegram_user_id=str(user_id), created_at__gte=since
    ).count() >= 10:
        enqueue(chat_id, RATE_LIMITED, markup=_home_markup())
        return False
    with transaction.atomic():
        complaint = Complaint.objects.create(
            governorate=region.governorate, region=region, title=title.strip(), body=body.strip(),
            kind=(kind or "")[:40],
            latitude=Decimal(str(latitude)) if latitude is not None else None,
            longitude=Decimal(str(longitude)) if longitude is not None else None,
            source=Complaint.Source.TELEGRAM, telegram_chat_id=str(chat_id), telegram_user_id=str(user_id), image=image,
        )
        notify_new_complaint(complaint)
        enqueue(chat_id, receipt(complaint.pk), markup=_menu_markup(chat_id))
    return complaint


def _publications(chat_id, text):
    if text in {"القائمة الاسترشادية", "قائمة الأسعار", "prices", "/prices"}:
        report = PriceReport.objects.order_by("-published_at").first()
        if report is None or not report.image:
            enqueue(chat_id, "لا توجد قائمة أسعار منشورة.", markup=_home_markup())
        else:
            enqueue(chat_id, photo=report.image.name, markup=_home_markup())
        return True
    if text in {"حركة المعابر", "crossings", "/crossings"}:
        report = CrossingReport.objects.order_by("-published_at").first()
        if report is None or (not report.body and not report.image):
            enqueue(chat_id, "لا توجد حركة معابر منشورة.", markup=_home_markup())
        elif report.image:
            enqueue(chat_id, photo=report.image.name, markup=_home_markup())
        else:
            enqueue(chat_id, report.body, markup=_home_markup())
        return True
    return False


HISTORY_PAGE = 15


def _history_rows(items, page, text_of, data_of, page_prefix):
    rows = _paged(items, page, text_of, data_of, page_prefix, page_size=HISTORY_PAGE)
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    return rows


def _crossing_history_label(report):
    from apps.publications.crossing_text import WEEKDAYS

    if report.movement_date:
        day = WEEKDAYS[report.movement_date.weekday()]
        return f"{report.movement_date.strftime('%d/%m/%Y')} {day}"
    return timezone.localtime(report.published_at).strftime("%d/%m/%Y")


def _price_history_label(report):
    stamp = timezone.localtime(report.published_at).strftime("%d/%m/%Y %H:%M")
    return f"{stamp} ({report.pk})"


def _crossing_history(chat_id, telegram_id, page):
    from apps.accounts.permissions import allows
    from django.db.models import F

    user = _linked_user(telegram_id)
    if user is None or not allows(user, "can_publish_crossings"):
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    items = list(CrossingReport.objects.order_by(F("movement_date").desc(nulls_last=True), "-published_at", "-pk"))
    if not items:
        enqueue(chat_id, "لا توجد حركة معابر منشورة.", markup=_home_markup())
        return
    enqueue(chat_id, "سجل الحركات", markup={"inline_keyboard": _history_rows(
        items, page, _crossing_history_label, lambda item: f"xi:{item.pk}", "xh",
    )})


def _price_history(chat_id, telegram_id, page):
    from apps.accounts.permissions import allows

    user = _linked_user(telegram_id)
    if user is None or not allows(user, "can_publish_prices"):
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    items = list(PriceReport.objects.order_by("-published_at", "-pk"))
    if not items:
        enqueue(chat_id, "لا توجد قائمة أسعار منشورة.", markup=_home_markup())
        return
    enqueue(chat_id, "سجل الأسعار", markup={"inline_keyboard": _history_rows(
        items, page, _price_history_label, lambda item: f"pi:{item.pk}", "ph",
    )})


def _open_crossing_history(chat_id, telegram_id, pk):
    from apps.accounts.permissions import allows

    user = _linked_user(telegram_id)
    report = CrossingReport.objects.filter(pk=pk).first()
    if user is None or not allows(user, "can_publish_crossings") or report is None:
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    back = {"inline_keyboard": [
        [{"text": "سجل الحركات", "callback_data": "xh:0"}],
        [{"text": "القائمة", "callback_data": "mn"}],
    ]}
    if report.image:
        enqueue(chat_id, photo=report.image.name, markup=back)
    elif report.body:
        enqueue(chat_id, report.body, markup=back)
    else:
        enqueue(chat_id, "لا توجد ورقة لهذا التاريخ.", markup=back)


def _open_price_history(chat_id, telegram_id, pk):
    from apps.accounts.permissions import allows

    user = _linked_user(telegram_id)
    report = PriceReport.objects.filter(pk=pk).first()
    if user is None or not allows(user, "can_publish_prices") or report is None or not report.image:
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    enqueue(chat_id, photo=report.image.name, markup={"inline_keyboard": [
        [{"text": "سجل الأسعار", "callback_data": "ph:0"}],
        [{"text": "القائمة", "callback_data": "mn"}],
    ]})


def _staff_action(chat_id, telegram_id, text):
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED, markup=_home_markup())
        return True
    bits = text.split(maxsplit=3)
    command = bits[0]
    try:
        complaint = Complaint.objects.get(pk=int(bits[1]))
        if command == "/accept":
            accept_complaint(complaint, user, channel="telegram", ip=None, telegram_id=str(telegram_id))
            notify_accept(complaint, user)
            _open_complaint(chat_id, telegram_id, complaint.pk)
            return True
        elif command == "/assign":
            inspector = User.objects.get(pk=int(bits[2]))
            assign_complaint(complaint, user, inspector, channel="telegram", ip=None, telegram_id=str(telegram_id))
        elif command == "/field":
            if len(bits) > 3 and bits[2] in {"governor", "legal"}:
                body = bits[3]
            else:
                body = text.split(maxsplit=2)[2]
            submit_field_report(
                complaint, user, body, [],
                channel="telegram", ip=None, telegram_id=str(telegram_id),
            )
        elif command == "/close":
            notes = text.split(maxsplit=2)[2] if len(text.split(maxsplit=2)) > 2 else ""
            close_legal(complaint, user, notes, channel="telegram", ip=None, telegram_id=str(telegram_id))
        else:
            return False
    except (Complaint.DoesNotExist, User.DoesNotExist, IndexError, ValueError, ValidationError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        enqueue(chat_id, message, markup=_home_markup())
        return True
    enqueue(chat_id, "تم التنفيذ.", markup=_home_markup())
    return True


ROLE_LABELS = {
    User.Role.ADMIN: "مدير النظام",
    User.Role.GOVERNOR: "مدير المحافظة",
    User.Role.INSPECTOR: "مفتش",
    User.Role.LEGAL: "الشؤون القانونية",
}


def _accepted_image(image):
    if image is None:
        return None
    name = (getattr(image, "name", "") or "").lower()
    if not name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return None
    if getattr(image, "size", 0) > 5 * 1024 * 1024:
        return None
    return image


def notify_return(complaint, actor):
    governors = User.objects.filter(
        role=User.Role.GOVERNOR, is_active=True, governorate_id=complaint.governorate_id,
        telegram_link__isnull=False,
    ).select_related("telegram_link")
    message = (
        "أُعيدت إليك شكوى لتوجيهها إلى مفتش آخر.\n"
        f"أرجعها: {actor.display_name or actor.username}\n"
        f"العنوان: {complaint.title}\n"
        f"المنطقة: {complaint.region.name}\n"
        f"السبب: {complaint.return_reason}"
    )
    opened = {"inline_keyboard": [[
        {"text": "توجيه", "callback_data": f"as:{complaint.pk}"},
        {"text": "فتح", "callback_data": f"op:{complaint.pk}"},
    ]]}
    for governor in governors:
        enqueue(governor.telegram_link.telegram_id, message, markup=opened)


def notify_accept(complaint, actor):
    governors = User.objects.filter(
        role=User.Role.GOVERNOR, is_active=True, governorate_id=complaint.governorate_id,
        telegram_link__isnull=False,
    ).select_related("telegram_link")
    message = f"قبل المفتش {actor.display_name or actor.username} الشكوى وتوجه للمتابعة الميدانية."
    for governor in governors:
        enqueue(governor.telegram_link.telegram_id, message)


def notify_citizen_resolved(complaint):
    _citizen_resolution(complaint)


def _citizen_resolution(complaint):
    if complaint.source == "whatsapp" and complaint.telegram_chat_id:
        from apps.whatsapp.client import send_text
        send_text(complaint.telegram_chat_id, f"تم التعامل مع الشكوى تبعك: {complaint.title}.")
        return
    if complaint.source == Complaint.Source.TELEGRAM and complaint.telegram_chat_id:
        enqueue(complaint.telegram_chat_id, f"تم التعامل مع الشكوى تبعك: {complaint.title}.", markup=_home_markup())


def _note(text, limit=800):
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _complaint_card(complaint):
    from apps.complaints.models import FollowUp

    body = (complaint.body or "").strip()
    if len(body) > 3000:
        body = body[:3000].rstrip() + "…"
    text = _detail_block(complaint, body) + f"\nالحالة: {complaint.status}"
    if complaint.inspector_name:
        text += f"\nالمفتش: {complaint.inspector_name}"
    finding = (
        complaint.follow_ups.filter(place=FollowUp.Place.FIELD)
        .order_by("-pk")
        .values_list("body", flat=True)
        .first()
    )
    if finding and finding.strip():
        text += f"\nنتيجة الكشف: {_note(finding)}"
    decision = (
        complaint.follow_ups.filter(place=FollowUp.Place.DECISION)
        .order_by("-pk")
        .values_list("body", flat=True)
        .first()
    )
    if decision and decision.strip():
        text += f"\nقرار مدير المحافظة: {_note(decision)}"
    if complaint.status == Complaint.Status.RECEIVED and complaint.return_reason:
        text += f"\nسبب الإرجاع: {complaint.return_reason}"
    return text


def _complaint_actions(user, complaint):
    from apps.complaints.models import FollowUp

    rows = []
    pending_reply = complaint.follow_ups.filter(place=FollowUp.Place.FIELD).exists()
    if (
        user.role == User.Role.INSPECTOR and complaint.status == Complaint.Status.RECEIVED
        and user.region_id == complaint.region_id and not complaint.returned_at
    ):
        rows.append([
            {"text": "قبول", "callback_data": f"/accept {complaint.pk}"},
            {"text": "رفض وإرجاع للمدير", "callback_data": f"rj:{complaint.pk}"},
        ])
    if (
        user.role == User.Role.INSPECTOR and complaint.status == Complaint.Status.FIELD
        and complaint.inspector_id == user.pk and not pending_reply
    ):
        rows.append([{"text": "رد", "callback_data": f"ry:{complaint.pk}"}])
    if (
        user.role == User.Role.GOVERNOR and complaint.status == Complaint.Status.FIELD
        and user.governorate_id == complaint.governorate_id and pending_reply
    ):
        rows.append([{"text": "إغلاق وإنهاء الشكوى", "callback_data": f"gc:{complaint.pk}"}])
        rows.append([{"text": "إحالة للشؤون القانونية", "callback_data": f"gl:{complaint.pk}"}])
    if (
        user.role == User.Role.GOVERNOR and complaint.status == Complaint.Status.RECEIVED
        and user.governorate_id == complaint.governorate_id
    ):
        rows.append([{"text": "توجيه", "callback_data": f"as:{complaint.pk}"}])
    if user.role == User.Role.LEGAL and complaint.status == Complaint.Status.LEGAL:
        rows.append([{"text": "تم الانجاز", "callback_data": f"dn:{complaint.pk}"}])
    rows.append([
        {"text": "الشكاوى", "callback_data": "ls:a:0"},
        {"text": "القائمة", "callback_data": "mn"},
    ])
    return {"inline_keyboard": rows}


def _send_complaint(chat_id, user, complaint):
    if complaint.image:
        enqueue(chat_id, photo=complaint.image.name)
    enqueue(chat_id, _complaint_card(complaint), markup=_complaint_actions(user, complaint))


def _open_complaint(chat_id, telegram_id, pk):
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED, markup=_home_markup())
        return
    complaint = visible_complaints(user).filter(pk=pk).select_related("governorate", "region").first()
    if complaint is None:
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    _send_complaint(chat_id, user, complaint)


def _complaint_mark(status):
    if status == Complaint.Status.LEGAL:
        return "↪️"
    if status in {Complaint.Status.FINISHED, Complaint.Status.RESOLVED}:
        return "🔒"
    return "🟢"


def _show_work(chat_id, telegram_id, filt, page):
    _clear_field_draft(chat_id)
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED, markup=_home_markup())
        return
    open_statuses = [Complaint.Status.RECEIVED, Complaint.Status.FIELD]
    transferred = [Complaint.Status.LEGAL]
    closed = [Complaint.Status.FINISHED, Complaint.Status.RESOLVED]
    if filt == "a":
        visible = visible_complaints(user)
        if visible.filter(status__in=open_statuses).exists():
            filt = "o"
        elif visible.filter(status__in=transferred).exists():
            filt = "t"
        else:
            filt = "c"
    filt = {"r": "o", "p": "t"}.get(filt, filt)
    buckets = {"o": open_statuses, "t": transferred, "c": closed}
    titles = {"o": "🟢 المفتوحة", "t": "↪️ المحولة", "c": "🔒 المغلقة"}
    empty = {
        "o": "لا توجد شكاوى مفتوحة.",
        "t": "لا توجد شكاوى محوّلة.",
        "c": "لا توجد شكاوى مغلقة.",
    }
    filters = [[
        {"text": "🟢 المفتوحة", "callback_data": "ls:o:0"},
        {"text": "↪️ المحولة", "callback_data": "ls:t:0"},
        {"text": "🔒 المغلقة", "callback_data": "ls:c:0"},
    ]]
    statuses = buckets.get(filt)
    if statuses is None:
        enqueue(chat_id, "بيانات غير صالحة.", markup=_home_markup())
        return
    items = list(
        visible_complaints(user).filter(status__in=statuses).select_related("region").order_by("-created_at")
    )
    footer = [[{"text": "القائمة", "callback_data": "mn"}]]
    if not items:
        enqueue(chat_id, empty[filt], markup={"inline_keyboard": filters + footer})
        return
    buttons = _paged(
        items, page,
        lambda item: (
            f"{_complaint_mark(item.status)} {item.pk} {item.title}"
            + (f" · {item.inspector_name}" if item.inspector_name else "")
        ),
        lambda item: f"op:{item.pk}",
        f"ls:{filt}",
        COMPLAINT_PAGE,
    )
    enqueue(
        chat_id,
        f"{titles[filt]}\nالعدد {len(items)}. مرّر اللوحة واختر شكوى للعمل عليها.",
        markup={"inline_keyboard": filters + buttons + footer},
    )


def _start_return(chat_id, telegram_id, pk):
    from apps.telegram.keyboard import keep_nav

    user = _linked_user(telegram_id)
    complaint = visible_complaints(user).filter(pk=pk).first() if user else None
    if (
        user is None or complaint is None or user.role != User.Role.INSPECTOR
        or complaint.status != Complaint.Status.RECEIVED or complaint.returned_at
        or user.region_id != complaint.region_id
    ):
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "reject_reason", "payload": {}})
    draft.step = "reject_reason"
    draft.payload = keep_nav(draft.payload, {"reject_complaint": complaint.pk})
    draft.save(update_fields=["step", "payload", "updated_at"])
    enqueue(chat_id, "اكتب سبب الرفض والإرجاع.", markup={"inline_keyboard": []})


def _finish_return(chat_id, telegram_id, pk, reason):
    from apps.telegram.keyboard import keep_nav

    user = _linked_user(telegram_id)
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    try:
        complaint = Complaint.objects.get(pk=pk)
        return_complaint(
            complaint, user, reason, channel="telegram", ip=None, telegram_id=str(telegram_id),
        )
    except (Complaint.DoesNotExist, ValidationError, AttributeError, TypeError, ValueError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "غير مسموح."
        enqueue(chat_id, message, markup=_home_markup())
        return
    if draft:
        draft.step = ""
        draft.payload = keep_nav(draft.payload, {})
        draft.save(update_fields=["step", "payload", "updated_at"])
    notify_return(complaint, user)
    enqueue(chat_id, "تم إرجاع الشكوى إلى مدير المحافظة.", markup=_home_markup())


def _start_reply(chat_id, telegram_id, pk):
    user = _linked_user(telegram_id)
    complaint = Complaint.objects.filter(pk=pk).first()
    if (
        user is None or complaint is None or user.role != User.Role.INSPECTOR
        or complaint.inspector_id != user.pk or complaint.status != Complaint.Status.FIELD
    ):
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "field_text", "payload": {}})
    draft.step = "field_text"
    draft.payload = {"field_complaint": complaint.pk}
    draft.save(update_fields=["step", "payload", "updated_at"])
    enqueue(chat_id, "اكتب نتيجة الكشف.", markup=_home_markup())


def _commit_field_report(chat_id, telegram_id, pk, text, draft):
    user = _linked_user(telegram_id)
    if user is None or not (text or "").strip():
        enqueue(chat_id, "اكتب نتيجة الكشف." if user else UNLINKED, markup=_home_markup())
        return
    try:
        complaint = Complaint.objects.get(pk=pk)
        submit_field_report(
            complaint, user, text, _field_files(draft) if draft else [],
            channel="telegram", ip=None, telegram_id=str(telegram_id),
        )
    except (Complaint.DoesNotExist, ValidationError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        enqueue(chat_id, message, markup=_home_markup())
        return
    if draft:
        draft.delete()
    enqueue(chat_id, "أُرسلت نتيجة الكشف إلى مدير المحافظة.", markup=_home_markup())


def _governor_decide(chat_id, telegram_id, pk, decision):
    from apps.complaints.services import decide_complaint

    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED, markup=_home_markup())
        return
    try:
        complaint = Complaint.objects.get(pk=pk)
        decide_complaint(
            complaint, user, decision, channel="telegram", ip=None, telegram_id=str(telegram_id),
        )
    except (Complaint.DoesNotExist, ValidationError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        enqueue(chat_id, message, markup=_home_markup())
        return
    done = "أُغلقت الشكوى وأُنهيت." if decision == "close" else "أُحيلت الشكوى إلى الشؤون القانونية."
    enqueue(chat_id, done, markup=_home_markup())


def _show_inspectors(chat_id, telegram_id, pk, page):
    user = _linked_user(telegram_id)
    complaint = Complaint.objects.filter(pk=pk).first()
    if (
        user is None or complaint is None or user.role != User.Role.GOVERNOR
        or user.governorate_id != complaint.governorate_id or complaint.status != Complaint.Status.RECEIVED
    ):
        enqueue(chat_id, "غير مسموح.", markup=_home_markup())
        return
    inspectors = list(User.objects.filter(
        role=User.Role.INSPECTOR, is_active=True, region_id=complaint.region_id,
    ).order_by("display_name", "username"))
    if not inspectors:
        enqueue(chat_id, "لا يوجد مفتش مفعّل في هذه المنطقة.", markup=_home_markup())
        return
    rows = _paged(
        inspectors, page,
        lambda item: item.display_name or item.username,
        lambda item: f"in:{complaint.pk}:{item.pk}",
        f"ap:{complaint.pk}",
    )
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    enqueue(chat_id, "اختر المفتش.", markup={"inline_keyboard": rows})


def _assign_to(chat_id, telegram_id, complaint_id, inspector_id):
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED, markup=_home_markup())
        return
    try:
        complaint = Complaint.objects.select_related("governorate", "region").get(pk=complaint_id)
        inspector = User.objects.get(pk=inspector_id)
        assign_complaint(complaint, user, inspector, channel="telegram", ip=None, telegram_id=str(telegram_id))
    except (Complaint.DoesNotExist, User.DoesNotExist, ValidationError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        enqueue(chat_id, message, markup=_home_markup())
        return
    enqueue(chat_id, "تم توجيه الشكوى إلى المفتش.", markup=_home_markup())
    link = TelegramLink.objects.filter(user=inspector).first()
    if link:
        _send_complaint(link.telegram_id, inspector, complaint)


def _legal_done(chat_id, telegram_id, pk):
    user = _linked_user(telegram_id)
    if user is None:
        enqueue(chat_id, UNLINKED, markup=_home_markup())
        return
    try:
        complaint = Complaint.objects.get(pk=pk)
        close_legal(complaint, user, "", channel="telegram", ip=None, telegram_id=str(telegram_id))
    except (Complaint.DoesNotExist, ValidationError) as error:
        message = error.messages[0] if isinstance(error, ValidationError) else "بيانات غير صالحة."
        enqueue(chat_id, message, markup=_home_markup())
        return
    enqueue(chat_id, "تم الانجاز وأُغلقت الشكوى.", markup=_home_markup())


def _field_files(draft):
    image = _image_file(draft)
    if image is None:
        return []
    name = (getattr(image, "name", "") or "").lower()
    if name.endswith(".png"):
        image.content_type = "image/png"
    elif name.endswith(".webp"):
        image.content_type = "image/webp"
    else:
        image.content_type = "image/jpeg"
    return [image]


def _image_file(draft):
    if not draft or not draft.payload.get("image"):
        return None
    return ContentFile(base64.b64decode(draft.payload["image"]), name=draft.payload["image_name"])


def _finish_draft(chat_id, user_id, draft):
    payload = draft.payload or {}
    if draft.step != "confirm" or not payload.get("kind"):
        enqueue(chat_id, "بيانات الشكوى غير مكتملة.", markup=_home_markup())
        return
    result = _create_complaint(
        chat_id, user_id, payload.get("governorate"), payload.get("region"),
        payload.get("title", ""), payload.get("body", ""), _image_file(draft),
        kind=payload.get("kind", ""), latitude=payload.get("latitude"), longitude=payload.get("longitude"),
    )
    if result:
        draft.delete()
    elif result is None:
        enqueue(chat_id, "بيانات الشكوى غير مكتملة.", markup=_home_markup())


def _advance_draft(chat_id, user_id, text):
    from apps.telegram.office import consume_text
    if consume_text(chat_id, user_id, text):
        return True
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or draft.step not in COMPLAINT_STEPS | {"field_text", "field_dest", "reject_reason"}:
        return False
    cleaned = text.strip()
    payload = dict(draft.payload)
    if draft.step == "reject_reason":
        if not cleaned:
            enqueue(chat_id, "اكتب سبب الرفض والإرجاع.", markup={"inline_keyboard": []})
            return True
        _finish_return(chat_id, user_id, payload.get("reject_complaint"), cleaned)
        return True
    if draft.step == "field_dest":
        stored = (payload.get("field_text") or cleaned).strip()
        _commit_field_report(chat_id, user_id, payload.get("field_complaint"), stored, draft)
        return True
    if draft.step == "field_text":
        if not cleaned:
            enqueue(chat_id, "اكتب نتيجة الكشف.", markup=_home_markup())
            return True
        _commit_field_report(chat_id, user_id, payload.get("field_complaint"), cleaned[:3500], draft)
        return True
    if draft.step == "kind":
        _show_kinds(chat_id)
        return True
    if draft.step == "kind_text":
        if not cleaned or len(cleaned) > KIND_LIMIT:
            _ask_kind_text(chat_id)
            return True
        payload["kind"] = cleaned
        payload["kind_mode"] = "other"
        draft.step = "governorate"
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _show_governorates(chat_id, 0)
        return True
    if draft.step == "governorate":
        governorate = Governorate.objects.filter(name=cleaned).first()
        if governorate is None:
            enqueue(chat_id, "المحافظة غير موجودة.", markup=_home_markup())
            return True
        payload["governorate"] = governorate.pk
        draft.step = "region"
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _show_regions(chat_id, 0)
        return True
    if draft.step == "region":
        region = Region.objects.filter(governorate_id=payload.get("governorate"), name=cleaned).first()
        if region is None:
            enqueue(chat_id, "المنطقة غير موجودة.", markup=_home_markup())
            return True
        payload["region"] = region.pk
        draft.step = "title"
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _ask_title(chat_id)
        return True
    if draft.step == "title":
        if not cleaned:
            _ask_title(chat_id)
            return True
        payload["title"] = cleaned
        draft.step = "body"
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _ask_body(chat_id)
        return True
    if draft.step == "body":
        if not cleaned:
            _ask_body(chat_id)
            return True
        payload["body"] = cleaned
        draft.step = "image"
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _ask_image(chat_id)
        return True
    if draft.step == "image":
        if cleaned == "تخطي":
            _skip_image(chat_id)
            return True
        _ask_image(chat_id, saved=bool(payload.get("image")))
        return True
    if draft.step == "location":
        if cleaned == "تخطي":
            _skip_location(chat_id)
            return True
        _ask_location(chat_id)
        return True
    if draft.step == "confirm":
        if cleaned == "تقديم":
            _finish_draft(chat_id, user_id, draft)
            return True
        _show_confirm(chat_id)
        return True
    return False


def _choose_governorate(chat_id, raw_id):
    try:
        governorate = Governorate.objects.get(pk=int(raw_id))
    except (Governorate.DoesNotExist, TypeError, ValueError):
        enqueue(chat_id, "المحافظة غير موجودة.", markup=_home_markup())
        return
    draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "region", "payload": {}})
    payload = dict(draft.payload)
    payload["governorate"] = governorate.pk
    payload.pop("region", None)
    draft.step = "region"
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    _show_regions(chat_id, 0)


def _choose_region(chat_id, raw_id):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    payload = dict(draft.payload) if draft else {}
    try:
        region = Region.objects.get(pk=int(raw_id), governorate_id=payload.get("governorate"))
    except (Region.DoesNotExist, TypeError, ValueError):
        enqueue(chat_id, "المنطقة غير موجودة.", markup=_home_markup())
        return
    if draft is None:
        draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "title", "payload": {}})
    payload["region"] = region.pk
    draft.step = "title"
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    _ask_title(chat_id)


def _skip_image(chat_id):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or draft.step != "image":
        _show_menu(chat_id)
        return
    payload = dict(draft.payload)
    payload.pop("image", None)
    payload.pop("image_name", None)
    draft.step = "location"
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    _ask_location(chat_id)


def _skip_location(chat_id):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or draft.step != "location":
        _show_menu(chat_id)
        return
    payload = dict(draft.payload)
    payload.pop("latitude", None)
    payload.pop("longitude", None)
    draft.step = "confirm"
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    _show_confirm(chat_id)


def _take_location(chat_id, latitude, longitude):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or draft.step != "location":
        enqueue(chat_id, "الموقع يُرفق في خطوة الموقع.", markup=_home_markup())
        return
    point = parse_point(latitude, longitude)
    if point is None:
        _ask_location(chat_id)
        return
    payload = dict(draft.payload)
    payload["latitude"], payload["longitude"] = point
    draft.step = "confirm"
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    _show_confirm(chat_id)


def _reset_complaint(chat_id):
    from apps.telegram.keyboard import keep_nav

    draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "kind", "payload": {}})
    payload = keep_nav(draft.payload, {})
    for key in ("kind", "kind_mode", "governorate", "region", "title", "body", "image", "image_name", "latitude", "longitude"):
        payload.pop(key, None)
    draft.step = "kind"
    draft.payload = payload
    draft.save(update_fields=["step", "payload", "updated_at"])
    _show_kinds(chat_id)


def _show_complaint_step(chat_id):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    step = draft.step if draft else ""
    if step == "kind":
        _show_kinds(chat_id)
    elif step == "kind_text":
        _ask_kind_text(chat_id)
    elif step == "governorate":
        _show_governorates(chat_id, 0)
    elif step == "region":
        _show_regions(chat_id, 0)
    elif step == "title":
        _ask_title(chat_id)
    elif step == "body":
        _ask_body(chat_id)
    elif step == "image":
        _ask_image(chat_id, saved=bool((draft.payload or {}).get("image")))
    elif step == "location":
        _ask_location(chat_id)
    elif step == "confirm":
        _show_confirm(chat_id)
    else:
        _reset_complaint(chat_id)


def _choose_kind(chat_id, data):
    draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "kind", "payload": {}})
    payload = dict(draft.payload)
    if data == "k:other":
        payload["kind_mode"] = "other"
        payload.pop("kind", None)
        draft.step = "kind_text"
        draft.payload = payload
        draft.save(update_fields=["payload", "step", "updated_at"])
        _ask_kind_text(chat_id)
        return
    label = FIXED_KINDS.get(data)
    if label is None:
        _show_kinds(chat_id)
        return
    payload["kind"] = label
    payload["kind_mode"] = "fixed"
    draft.step = "governorate"
    draft.payload = payload
    draft.save(update_fields=["payload", "step", "updated_at"])
    _show_governorates(chat_id, 0)


def _start_complaint(chat_id):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft and draft.step in COMPLAINT_STEPS:
        enqueue(chat_id, RESUME_PROMPT, markup={"inline_keyboard": resume_rows()})
        return
    _reset_complaint(chat_id)


def _rewind_draft(chat_id, user_id):
    """Step back inside a typed answer without leaving the whole flow."""
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None:
        return False
    payload = dict(draft.payload or {})
    if draft.step == "kind_text":
        draft.step = "kind"
        draft.save(update_fields=["step", "updated_at"])
        _show_kinds(chat_id)
        return True
    if draft.step == "governorate":
        if payload.get("kind_mode") == "other":
            draft.step = "kind_text"
            draft.save(update_fields=["step", "updated_at"])
            _ask_kind_text(chat_id)
        else:
            draft.step = "kind"
            draft.save(update_fields=["step", "updated_at"])
            _show_kinds(chat_id)
        return True
    if draft.step == "region":
        draft.step = "governorate"
        draft.save(update_fields=["step", "updated_at"])
        _show_governorates(chat_id, 0)
        return True
    if draft.step == "title":
        draft.step = "region"
        draft.save(update_fields=["step", "updated_at"])
        _show_regions(chat_id, 0)
        return True
    if draft.step == "body":
        draft.step = "title"
        draft.save(update_fields=["step", "updated_at"])
        _ask_title(chat_id)
        return True
    if draft.step == "image":
        draft.step = "body"
        draft.save(update_fields=["step", "updated_at"])
        _ask_body(chat_id)
        return True
    if draft.step == "location":
        draft.step = "image"
        draft.save(update_fields=["step", "updated_at"])
        _ask_image(chat_id, saved=bool(payload.get("image")))
        return True
    if draft.step == "confirm":
        draft.step = "location"
        draft.save(update_fields=["step", "updated_at"])
        _ask_location(chat_id)
        return True
    if draft.step == "field_dest":
        draft.step = "field_text"
        draft.save(update_fields=["step", "updated_at"])
        enqueue(chat_id, "اكتب نتيجة الكشف.", markup=_home_markup())
        return True
    if draft.step == "reject_reason":
        complaint_id = (draft.payload or {}).get("reject_complaint")
        draft.step = ""
        draft.save(update_fields=["step", "updated_at"])
        if complaint_id:
            _open_complaint(chat_id, user_id, complaint_id)
            return True
    if draft.step == "field_text":
        complaint_id = (draft.payload or {}).get("field_complaint")
        draft.step = ""
        draft.save(update_fields=["step", "updated_at"])
        if complaint_id:
            _open_complaint(chat_id, user_id, complaint_id)
            return True
    return False


def _on_callback(chat_id, user_id, data):
    from apps.telegram.keyboard import track

    data = track(chat_id, data)
    try:
        if data == "mn":
            _show_menu(chat_id)
        elif data == "nw":
            _start_complaint(chat_id)
        elif data in FIXED_KINDS or data == "k:other":
            _choose_kind(chat_id, data)
        elif data == "resume":
            _show_complaint_step(chat_id)
        elif data == "restart":
            _reset_complaint(chat_id)
        elif data == "locskip":
            _skip_location(chat_id)
        elif data == "pr":
            _publications(chat_id, "قائمة الأسعار")
        elif data == "cr":
            _publications(chat_id, "حركة المعابر")
        elif data.startswith("xh:"):
            _crossing_history(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("xi:"):
            _open_crossing_history(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("ph:"):
            _price_history(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("pi:"):
            _open_price_history(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("gp:"):
            _show_governorates(chat_id, int(data.split(":")[1]))
        elif data.startswith("g:"):
            _choose_governorate(chat_id, data.split(":")[1])
        elif data.startswith("np:"):
            _show_regions(chat_id, int(data.split(":")[1]))
        elif data.startswith("n:"):
            _choose_region(chat_id, data.split(":")[1])
        elif data == "sk":
            _skip_image(chat_id)
        elif data == "ok":
            draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
            if draft is None:
                enqueue(chat_id, "بيانات الشكوى غير مكتملة.", markup=_home_markup())
            else:
                _finish_draft(chat_id, user_id, draft)
        elif data == "cq":
            _show_work(chat_id, user_id, "a", 0)
        elif data.startswith("ls:"):
            _, filt, page = data.split(":")
            _show_work(chat_id, user_id, filt, int(page))
        elif data.startswith("op:"):
            _open_complaint(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("ry:"):
            _start_reply(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("rj:"):
            _start_return(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("gc:") or data.startswith("dg:"):
            _governor_decide(chat_id, user_id, int(data.split(":")[1]), "close")
        elif data.startswith("gl:") or data.startswith("dl:"):
            _governor_decide(chat_id, user_id, int(data.split(":")[1]), "legal")
        elif data.startswith("as:"):
            _show_inspectors(chat_id, user_id, int(data.split(":")[1]), 0)
        elif data.startswith("ap:"):
            _, complaint_id, page = data.split(":")
            _show_inspectors(chat_id, user_id, int(complaint_id), int(page))
        elif data.startswith("in:"):
            _, complaint_id, inspector_id = data.split(":")
            _assign_to(chat_id, user_id, int(complaint_id), int(inspector_id))
        elif data.startswith("dn:"):
            _legal_done(chat_id, user_id, int(data.split(":")[1]))
        else:
            from apps.telegram.office import handle_callback
            if not handle_callback(chat_id, user_id, data):
                return False
    except (ValueError, IndexError):
        enqueue(chat_id, "بيانات غير صالحة.", markup=_home_markup())
    return True


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


def _answer_callback(callback):
    callback_id = callback.get("id")
    token = _value("TELEGRAM_BOT_TOKEN")
    if not callback_id or not token:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_id},
            timeout=10,
        )
    except Exception:
        return


def handle_update(update):
    callback = update.get("callback_query") or {}
    _answer_callback(callback)
    message = update.get("message") or callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    sender = (update.get("message") or {}).get("from") or callback.get("from") or {}
    user_id = sender.get("id")
    from apps.telegram.presence import touch
    try:
        touch(user_id, sender.get("username"))
    except Exception:
        pass
    text = (update.get("message") or {}).get("text") or callback.get("data") or ""
    if chat_id is None:
        return
    incoming = update.get("message") or {}
    if not callback.get("data") and incoming.get("location"):
        point = incoming["location"]
        _take_location(chat_id, point.get("latitude"), point.get("longitude"))
        return
    if not callback.get("data") and incoming.get("web_app_data"):
        try:
            sent = json.loads(incoming["web_app_data"].get("data") or "")
        except json.JSONDecodeError:
            sent = {}
        _take_location(chat_id, sent.get("latitude"), sent.get("longitude"))
        return
    photo = incoming.get("photo")
    if photo and not callback.get("data"):
        from apps.telegram.office import consume_photo
        if consume_photo(chat_id, user_id, photo):
            return
        draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
        downloaded = None
        if draft and draft.step in {"image", "field_text", "field_dest"}:
            try:
                downloaded = _download_photo(photo)
            except Exception:
                downloaded = None
            if downloaded:
                draft.payload = {**draft.payload, **downloaded}
                draft.save(update_fields=["payload", "updated_at"])
        if draft and draft.step == "image":
            if downloaded:
                draft.step = "location"
                draft.save(update_fields=["step", "updated_at"])
                _ask_location(chat_id, saved=True)
            else:
                _ask_image(chat_id)
        elif draft and draft.step == "field_dest":
            draft.step = "field_text"
            draft.save(update_fields=["step", "updated_at"])
            enqueue(chat_id, "تم حفظ الصورة. اكتب نتيجة الكشف." if downloaded else "اكتب نتيجة الكشف.", markup=_home_markup())
        elif draft and draft.step == "field_text":
            enqueue(chat_id, "تم حفظ الصورة. اكتب نتيجة الكشف." if downloaded else "اكتب نتيجة الكشف.", markup=_home_markup())
        elif draft and draft.step == "reject_reason":
            enqueue(chat_id, "اكتب سبب الرفض والإرجاع.", markup={"inline_keyboard": []})
        else:
            if downloaded is None:
                try:
                    downloaded = _download_photo(photo)
                except Exception:
                    downloaded = None
            if downloaded:
                draft, _ = TelegramDraft.objects.get_or_create(chat_id=str(chat_id), defaults={"step": "image", "payload": {}})
                draft.payload = {**draft.payload, **downloaded}
                draft.save(update_fields=["payload", "updated_at"])
                if draft.step == "image":
                    _ask_image(chat_id, saved=True)
                    return
            enqueue(chat_id, "الصورة تُرفق بعد نص الشكوى.", markup=_home_markup())
        return
    if callback.get("data"):
        if text.startswith(("/accept", "/assign", "/field", "/close")):
            _staff_action(chat_id, user_id, text)
        elif not _on_callback(chat_id, user_id, text):
            enqueue(chat_id, "بيانات غير صالحة.", markup=_home_markup())
        return
    if text.startswith("/start "):
        if consume_staff_link(text.split(maxsplit=1)[1], user_id):
            try:
                touch(user_id, sender.get("username"))
            except Exception:
                pass
            user = _linked_user(user_id)
            name = user.display_name or user.username
            enqueue(chat_id, f"تم ربط الحساب: {name}. الدور: {ROLE_LABELS.get(user.role, user.role)}.")
            _show_menu(chat_id)
        else:
            enqueue(chat_id, "رابط الربط غير صالح أو منتهي.", markup=_home_markup())
        return
    if text.startswith("/complaint"):
        _handle_complaint_command(chat_id, user_id, text)
        return
    if text.startswith(("/accept", "/assign", "/field", "/close")):
        _staff_action(chat_id, user_id, text)
        return
    if text == "/start":
        _show_menu(chat_id, welcome=True)
        return
    if text == "رجوع":
        if not _rewind_draft(chat_id, user_id):
            _on_callback(chat_id, user_id, "bk")
        return
    if text == "القائمة":
        _show_menu(chat_id)
        return
    if text in {"شكاوى", "وصلت", "المفتوحة", "🟢 المفتوحة"}:
        _on_callback(chat_id, user_id, "ls:o:0")
        return
    if text in {"معلقة", "المحولة", "↪️ المحولة"}:
        _on_callback(chat_id, user_id, "ls:t:0")
        return
    if text in {"مغلقة", "المقفلة", "المغلقة", "🔒 المغلقة"}:
        _on_callback(chat_id, user_id, "ls:c:0")
        return
    if text == "تقديم شكوى":
        _start_complaint(chat_id)
        return
    if text in {"إدخال تقرير", "نشر المعابر"}:
        _on_callback(chat_id, user_id, "crb")
        return
    if text == "نشر الأسعار":
        _on_callback(chat_id, user_id, "prb")
        return
    if text == "سجل الحركات":
        _on_callback(chat_id, user_id, "xh:0")
        return
    if text == "سجل الأسعار":
        _on_callback(chat_id, user_id, "ph:0")
        return
    from apps.telegram.keyboard import bound_action

    action = bound_action(chat_id, text) if text else None
    if action:
        if action.startswith(("/accept", "/assign", "/field", "/close")):
            _staff_action(chat_id, user_id, action)
        elif not _on_callback(chat_id, user_id, action):
            enqueue(chat_id, "بيانات غير صالحة.", markup=_home_markup())
        return
    if _publications(chat_id, text):
        return
    if text and _advance_draft(chat_id, user_id, text):
        return
    if text:
        _show_menu(chat_id)
