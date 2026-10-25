import base64

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.files.base import ContentFile

from apps.accounts.models import StaffRole, User
from apps.accounts.permissions import allows
from apps.common.models import SystemSettings
from apps.field_missions.models import FieldMission
from apps.field_missions.services import MissionError, close_mission, open_mission, redirect_mission, reply_mission, visible_missions
from apps.geography.models import Governorate, Region
from apps.publications.models import CrossingReport, PriceReport
from apps.telegram.models import TelegramDraft, TelegramWebhookStatus


def _say(chat_id, text, markup=None):
    from apps.telegram.webhook import enqueue
    enqueue(chat_id, text, markup=markup or _home())


def _home():
    return {"inline_keyboard": [[{"text": "القائمة", "callback_data": "mn"}]]}


def _user(telegram_id):
    from apps.telegram.webhook import _linked_user
    return _linked_user(telegram_id)


def _draft(chat_id):
    draft, _created = TelegramDraft.objects.get_or_create(
        chat_id=str(chat_id), defaults={"step": "office", "payload": {}},
    )
    return draft


def _save(draft, step, payload):
    draft.step = step
    draft.payload = payload
    draft.save(update_fields=["step", "payload", "updated_at"])


def extra_rows(user):
    rows = []
    if allows(user, "can_view_field_missions"):
        row = [{"text": "المهمات", "callback_data": "ms:0"}]
        if user.role != User.Role.LEGAL and allows(user, "can_open_field_missions"):
            row.append({"text": "إنشاء مهمة", "callback_data": "mc"})
        rows.append(row)
    if allows(user, "can_publish"):
        rows.append([
            {"text": "نشر الأسعار", "callback_data": "prb"},
            {"text": "نشر المعابر", "callback_data": "crb"},
        ])
    if user.role == User.Role.GOVERNOR or allows(user, "can_view_reports"):
        rows.append([{"text": "التقارير", "callback_data": "rp"}])
    if allows(user, "can_manage_users"):
        rows.append([{"text": "المستخدمون", "callback_data": "us:0"}])
    if allows(user, "can_manage_geography"):
        rows.append([
            {"text": "المحافظات", "callback_data": "gv:0"},
            {"text": "المناطق", "callback_data": "rg:0"},
        ])
    if allows(user, "can_manage_settings"):
        rows.append([{"text": "إعدادات النظام", "callback_data": "st"}])
    return rows


def handle_callback(chat_id, user_id, data):
    user = _user(user_id)
    if data.startswith("ms:"):
        _missions(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("mo:"):
        _open_mission_card(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("my:"):
        _start_mission_reply(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("mf:") or data.startswith("mq:"):
        _finish_mission_reply(chat_id, user, int(data.split(":")[1]), "finished" if data.startswith("mf:") else "legal")
    elif data.startswith("md:"):
        _mission_inspectors(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("mi:"):
        _, mission_id, inspector_id = data.split(":")
        _redirect(chat_id, user, int(mission_id), int(inspector_id))
    elif data.startswith("mz:"):
        _close_mission_card(chat_id, user, int(data.split(":")[1]))
    elif data == "mc":
        _start_mission(chat_id, user)
    elif data.startswith("mk:") or data.startswith("mp:") or data.startswith("mx:") or data.startswith("mg:") or data.startswith("mu:"):
        _mission_choice(chat_id, user, data)
    elif data == "prb":
        _ask_price(chat_id, user)
    elif data == "crb":
        _ask_crossing(chat_id, user)
    elif data == "crok":
        _publish_crossing(chat_id, user, image=None)
    elif data == "rp" or data == "rpw":
        _report(chat_id, user, week=data == "rpw")
    elif data.startswith("us:"):
        _users(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("ut:"):
        _toggle_user(chat_id, user, int(data.split(":")[1]))
    elif data == "uc":
        _user_roles(chat_id, user)
    elif data.startswith("ur:"):
        _pick_user_role(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("ug:") or data.startswith("un:"):
        _user_place(chat_id, user, data)
    elif data.startswith("gv:"):
        _governorates(chat_id, user, int(data.split(":")[1]))
    elif data == "ga":
        _ask(chat_id, user, "office_gov_name", "أرسل اسم المحافظة.")
    elif data.startswith("rg:"):
        _region_governorates(chat_id, user, int(data.split(":")[1]))
    elif data.startswith("rgg:"):
        _ask_region_name(chat_id, user, int(data.split(":")[1]))
    elif data == "st":
        _settings(chat_id, user)
    elif data == "sw":
        _toggle_web_complaints(chat_id, user)
    else:
        return False
    return True


def consume_text(chat_id, user_id, text):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or not str(draft.step).startswith("office_"):
        return False
    user = _user(user_id)
    if user is None:
        _say(chat_id, "هذا الحساب غير مربوط. اطلب رابط الربط من مدير النظام.")
        return True
    cleaned = text.strip()
    payload = dict(draft.payload)
    step = draft.step
    if step == "office_reply":
        payload["mission_text"] = cleaned[:3500]
        _save(draft, "office_reply_dest", payload)
        _say(chat_id, "اختر نتيجة المهمة.", markup={"inline_keyboard": [
            [{"text": "منتهية", "callback_data": f"mf:{payload['mission']}"}],
            [{"text": "للشؤون القانونية", "callback_data": f"mq:{payload['mission']}"}],
            [{"text": "القائمة", "callback_data": "mn"}],
        ]})
    elif step == "office_place":
        payload["place_name"] = cleaned
        _save(draft, "office_phone", payload)
        _say(chat_id, "أرسل رقم الجوال.")
    elif step == "office_phone":
        payload["phone"] = cleaned
        _save(draft, "office_details", payload)
        _say(chat_id, "أرسل تفاصيل المهمة.")
    elif step == "office_details":
        payload["details"] = cleaned
        _create_mission(chat_id, user, draft, payload)
    elif step == "office_cross":
        payload["body"] = cleaned
        _save(draft, "office_cross_ready", payload)
        _say(chat_id, "اضغط نشر، أو أرسل صورة مع النص.", markup={"inline_keyboard": [
            [{"text": "نشر", "callback_data": "crok"}],
            [{"text": "القائمة", "callback_data": "mn"}],
        ]})
    elif step == "office_user_name":
        payload["username"] = cleaned
        _save(draft, "office_user_password", payload)
        _say(chat_id, "أرسل كلمة المرور، 12 محرفاً على الأقل.")
    elif step == "office_user_password":
        _create_user(chat_id, user, draft, payload, cleaned)
    elif step == "office_gov_name":
        if not allows(user, "can_manage_geography") or not cleaned:
            _say(chat_id, "غير مسموح.")
            return True
        try:
            Governorate.objects.create(name=cleaned)
        except IntegrityError:
            _say(chat_id, "اسم المحافظة مستخدم.")
            return True
        draft.delete()
        _say(chat_id, "تمت إضافة المحافظة.")
    elif step == "office_region_name":
        if not allows(user, "can_manage_geography") or not cleaned:
            _say(chat_id, "غير مسموح.")
            return True
        Region.objects.create(governorate_id=payload["governorate"], name=cleaned)
        draft.delete()
        _say(chat_id, "تمت إضافة المنطقة.")
    else:
        _say(chat_id, "اختر من الأزرار.")
    return True


def consume_photo(chat_id, user_id, photo):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None or draft.step not in {"office_price", "office_cross_ready"}:
        return False
    from apps.telegram.webhook import _download_photo
    try:
        downloaded = _download_photo(photo)
    except Exception:
        downloaded = None
    user = _user(user_id)
    if user is None or not downloaded:
        _say(chat_id, "تعذر حفظ الصورة.")
        return True
    image = _image(downloaded)
    if draft.step == "office_price":
        if not allows(user, "can_publish"):
            _say(chat_id, "غير مسموح.")
            return True
        PriceReport.objects.create(image=image, publisher=user, publisher_name=user.display_name or user.username)
        draft.delete()
        _say(chat_id, "تم نشر قائمة الأسعار.")
    else:
        _publish_crossing(chat_id, user, image)
    return True


def _missions(chat_id, user, page):
    if user is None or not allows(user, "can_view_field_missions"):
        _say(chat_id, "غير مسموح.")
        return
    items = list(visible_missions(user).order_by("-created_at"))
    if not items:
        _say(chat_id, "لا توجد مهمات.")
        return
    from apps.telegram.webhook import _paged
    rows = _paged(items, page, lambda item: f"{item.place_name} · {item.status}", lambda item: f"mo:{item.pk}", "ms")
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "اختر المهمة.", markup={"inline_keyboard": rows})


def _open_mission_card(chat_id, user, pk):
    mission = _visible_mission(user, pk)
    if mission is None:
        _say(chat_id, "غير مسموح.")
        return
    _say(chat_id, _mission_text(mission), markup=_mission_actions(user, mission))


def _mission_text(mission):
    details = (mission.details or "").strip()
    if len(details) > 2500:
        details = details[:2500].rstrip() + "…"
    return (
        f"النوع: {mission.kind}\n"
        f"الأولوية: {mission.priority}\n"
        f"المحل: {mission.place_name}\n"
        f"الجوال: {mission.phone}\n"
        f"التفاصيل: {details}\n"
        f"الحالة: {mission.status}"
    )


def _mission_actions(user, mission):
    rows = []
    assigned = mission.assignees.filter(user=user).exists()
    if user.role == User.Role.INSPECTOR and assigned and mission.status == FieldMission.Status.FIELD:
        rows.append([{"text": "رد", "callback_data": f"my:{mission.pk}"}])
    if user.role == User.Role.GOVERNOR and mission.status == FieldMission.Status.OFFICE and user.governorate_id == mission.governorate_id:
        rows.append([{"text": "توجيه", "callback_data": f"md:{mission.pk}"}])
    if user.role == User.Role.LEGAL and mission.status == FieldMission.Status.LEGAL:
        rows.append([{"text": "تم المعالجة", "callback_data": f"mz:{mission.pk}"}])
    rows.append([{"text": "المهمات", "callback_data": "ms:0"}, {"text": "القائمة", "callback_data": "mn"}])
    return {"inline_keyboard": rows}


def _visible_mission(user, pk):
    if user is None or not allows(user, "can_view_field_missions"):
        return None
    return visible_missions(user).filter(pk=pk).first()


def _start_mission_reply(chat_id, user, pk):
    mission = _visible_mission(user, pk)
    if mission is None or user.role != User.Role.INSPECTOR or not mission.assignees.filter(user=user).exists():
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    _save(draft, "office_reply", {"mission": mission.pk})
    _say(chat_id, "اكتب رد المهمة.")


def _finish_mission_reply(chat_id, user, pk, destination):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    text = (draft.payload.get("mission_text") or "").strip() if draft and draft.payload.get("mission") == pk else ""
    mission = _visible_mission(user, pk)
    if mission is None or not text:
        _say(chat_id, "اكتب رد المهمة.")
        return
    try:
        reply_mission(user, mission, text, [], destination)
    except MissionError as error:
        _say(chat_id, error.message)
        return
    if draft:
        draft.delete()
    _say(chat_id, "تم إرسال رد المهمة.")


def _mission_inspectors(chat_id, user, pk):
    mission = _visible_mission(user, pk)
    if mission is None or user.role != User.Role.GOVERNOR:
        _say(chat_id, "غير مسموح.")
        return
    inspectors = list(User.objects.filter(
        role=User.Role.INSPECTOR, is_active=True, governorate_id=mission.governorate_id,
    ).order_by("display_name", "username"))
    if not inspectors:
        _say(chat_id, "لا يوجد مفتش مفعّل في هذه المحافظة.")
        return
    rows = [[{"text": (item.display_name or item.username)[:40], "callback_data": f"mi:{mission.pk}:{item.pk}"}] for item in inspectors[:8]]
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "اختر المفتش.", markup={"inline_keyboard": rows})


def _redirect(chat_id, user, mission_id, inspector_id):
    mission = _visible_mission(user, mission_id)
    if mission is None:
        _say(chat_id, "غير مسموح.")
        return
    try:
        redirect_mission(user, mission, inspector_id)
    except MissionError as error:
        _say(chat_id, error.message)
        return
    _say(chat_id, "تم توجيه المهمة.")


def _close_mission_card(chat_id, user, pk):
    mission = _visible_mission(user, pk)
    if mission is None:
        _say(chat_id, "غير مسموح.")
        return
    try:
        close_mission(user, mission, "")
    except MissionError as error:
        _say(chat_id, error.message)
        return
    _say(chat_id, "تم المعالجة وأُغلقت المهمة.")


def _start_mission(chat_id, user):
    if user is None or user.role == User.Role.LEGAL or not allows(user, "can_open_field_missions"):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    _save(draft, "office_kind", {})
    _choice_buttons(chat_id, "اختر نوع المهمة.", list(FieldMission.Kind.values), "mk")


def _mission_choice(chat_id, user, data):
    if user is None or not allows(user, "can_open_field_missions"):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    payload = dict(draft.payload)
    prefix, raw = data.split(":", 1)
    if prefix == "mk":
        payload["kind"] = list(FieldMission.Kind.values)[int(raw)]
        _save(draft, "office_priority", payload)
        _choice_buttons(chat_id, "اختر أولوية المهمة.", list(FieldMission.Priority.values), "mp")
    elif prefix == "mp":
        payload["priority"] = list(FieldMission.Priority.values)[int(raw)]
        _save(draft, "office_scope", payload)
        _after_priority(chat_id, user, draft, payload)
    elif prefix == "mg":
        payload["governorate"] = int(raw)
        _save(draft, "office_scope", payload)
        _scope_buttons(chat_id)
    elif prefix == "mx":
        payload["scope"] = {"1": "one", "2": "all", "3": "office"}.get(raw, raw)
        _save(draft, "office_scope", payload)
        if payload["scope"] == "one":
            _new_mission_inspectors(chat_id, user, payload)
        else:
            _save(draft, "office_place", payload)
            _say(chat_id, "أرسل اسم المحل.")
    elif prefix == "mu":
        payload["inspector"] = int(raw)
        _save(draft, "office_place", payload)
        _say(chat_id, "أرسل اسم المحل.")


def _after_priority(chat_id, user, draft, payload):
    if user.role == User.Role.INSPECTOR:
        _save(draft, "office_place", payload)
        _say(chat_id, "أرسل اسم المحل.")
        return
    if user.role in {User.Role.ADMIN, User.Role.CUSTOM} and not payload.get("governorate"):
        items = list(Governorate.objects.order_by("name"))
        rows = [[{"text": item.name[:40], "callback_data": f"mg:{item.pk}"}] for item in items[:8]]
        rows.append([{"text": "القائمة", "callback_data": "mn"}])
        _say(chat_id, "اختر المحافظة.", markup={"inline_keyboard": rows})
        return
    _scope_buttons(chat_id)


def _scope_buttons(chat_id):
    _say(chat_id, "اختر جهة المهمة.", markup={"inline_keyboard": [
        [{"text": "مفتش واحد", "callback_data": "mx:1"}],
        [{"text": "كل المفتشين", "callback_data": "mx:2"}],
        [{"text": "إدارة المحافظة", "callback_data": "mx:3"}],
        [{"text": "القائمة", "callback_data": "mn"}],
    ]})


def _new_mission_inspectors(chat_id, user, payload):
    governorate_id = payload.get("governorate") or getattr(user, "governorate_id", None)
    inspectors = list(User.objects.filter(
        role=User.Role.INSPECTOR, is_active=True, governorate_id=governorate_id,
    ).order_by("display_name", "username"))
    if not inspectors:
        _say(chat_id, "لا يوجد مفتش مفعّل في هذه المحافظة.")
        return
    rows = [[{"text": (item.display_name or item.username)[:40], "callback_data": f"mu:{item.pk}"}] for item in inspectors[:8]]
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "اختر المفتش.", markup={"inline_keyboard": rows})


def _create_mission(chat_id, user, draft, payload):
    body = {
        "kind": payload.get("kind"),
        "priority": payload.get("priority"),
        "details": payload.get("details"),
        "place_name": payload.get("place_name"),
        "phone": payload.get("phone"),
        "scope": payload.get("scope") or "one",
        "governorate": payload.get("governorate"),
        "inspector": payload.get("inspector"),
    }
    try:
        open_mission(user, body)
    except MissionError as error:
        _say(chat_id, error.message)
        return
    draft.delete()
    _say(chat_id, "تم فتح المهمة.")


def _choice_buttons(chat_id, title, values, prefix):
    rows = [[{"text": value[:40], "callback_data": f"{prefix}:{index}"}] for index, value in enumerate(values)]
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, title, markup={"inline_keyboard": rows})


def _ask_price(chat_id, user):
    if user is None or not allows(user, "can_publish"):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    _save(draft, "office_price", {})
    _say(chat_id, "أرسل صورة قائمة الأسعار.")


def _ask_crossing(chat_id, user):
    if user is None or not allows(user, "can_publish"):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    _save(draft, "office_cross", {})
    _say(chat_id, "أرسل نص حركة المعابر.")


def _publish_crossing(chat_id, user, image):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    body = (draft.payload.get("body") or "").strip() if draft else ""
    if user is None or not allows(user, "can_publish") or (not body and image is None):
        _say(chat_id, "أرسل نص حركة المعابر.")
        return
    CrossingReport.objects.create(
        body=body, image=image, publisher=user, publisher_name=user.display_name or user.username,
    )
    if draft:
        draft.delete()
    _say(chat_id, "تم نشر حركة المعابر.")


def _report(chat_id, user, week):
    if user is None or not (user.role == User.Role.GOVERNOR or allows(user, "can_view_reports")):
        _say(chat_id, "غير مسموح.")
        return
    from datetime import timedelta
    from apps.reports.queries import _today, overview
    today = _today()
    start = today - timedelta(days=6) if week else today
    data = overview(user, {"date_from": start.isoformat(), "date_to": today.isoformat()})
    label = "آخر 7 أيام" if week else "اليوم"
    _say(
        chat_id,
        f"تقرير {label}\nالجديدة: {data['created']}\nالمنجزة: {data['done']}\nالمعلقة: {data['pending_at_end']}",
        markup={"inline_keyboard": [
            [{"text": "اليوم", "callback_data": "rp"}, {"text": "آخر 7 أيام", "callback_data": "rpw"}],
            [{"text": "القائمة", "callback_data": "mn"}],
        ]},
    )


def _users(chat_id, user, page):
    if user is None or not allows(user, "can_manage_users"):
        _say(chat_id, "غير مسموح.")
        return
    people = list(User.objects.order_by("username"))
    chunk = people[page * 6:(page + 1) * 6]
    rows = [[
        {"text": f"{item.username} · {'مفعّل' if item.is_active else 'موقوف'}"[:40], "callback_data": f"ut:{item.pk}"},
    ] for item in chunk]
    nav = []
    if page:
        nav.append({"text": "السابق", "callback_data": f"us:{page - 1}"})
    if (page + 1) * 6 < len(people):
        nav.append({"text": "التالي", "callback_data": f"us:{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "إنشاء مستخدم", "callback_data": "uc"}, {"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "اختر مستخدماً لتفعيل حسابه أو إيقافه.", markup={"inline_keyboard": rows})


def _toggle_user(chat_id, user, pk):
    if user is None or not allows(user, "can_manage_users"):
        _say(chat_id, "غير مسموح.")
        return
    target = User.objects.filter(pk=pk).first()
    if target is None:
        _say(chat_id, "المستخدم غير موجود.")
        return
    if target.is_active and target.role == User.Role.ADMIN and User.objects.filter(role=User.Role.ADMIN, is_active=True).count() == 1:
        _say(chat_id, "لا يمكن تعطيل آخر مدير نظام مفعّل.")
        return
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    _say(chat_id, "تم تحديث المستخدم.")


def _user_roles(chat_id, user):
    if user is None or not allows(user, "can_manage_users"):
        _say(chat_id, "غير مسموح.")
        return
    roles = list(StaffRole.objects.order_by("pk"))
    rows = [[{"text": role.name[:40], "callback_data": f"ur:{role.pk}"}] for role in roles[:8]]
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "اختر الدور.", markup={"inline_keyboard": rows})


def _pick_user_role(chat_id, user, role_id):
    if user is None or not allows(user, "can_manage_users"):
        _say(chat_id, "غير مسموح.")
        return
    role = StaffRole.objects.filter(pk=role_id).first()
    if role is None:
        _say(chat_id, "الدور غير موجود.")
        return
    if role.kind == "admin" or (user.role != User.Role.ADMIN and role.kind == User.Role.ADMIN):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    payload = {"role_id": role.pk, "kind": role.kind}
    if role.kind in {StaffRole.Kind.GOVERNOR, StaffRole.Kind.INSPECTOR}:
        _save(draft, "office_user_gov", payload)
        items = list(Governorate.objects.order_by("name"))
        rows = [[{"text": item.name[:40], "callback_data": f"ug:{item.pk}"}] for item in items[:8]]
        rows.append([{"text": "القائمة", "callback_data": "mn"}])
        _say(chat_id, "اختر المحافظة.", markup={"inline_keyboard": rows})
        return
    _save(draft, "office_user_name", payload)
    _say(chat_id, "أرسل اسم الدخول.")


def _user_place(chat_id, user, data):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if user is None or draft is None:
        _say(chat_id, "غير مسموح.")
        return
    payload = dict(draft.payload)
    prefix, raw = data.split(":", 1)
    if prefix == "ug":
        payload["governorate"] = int(raw)
        if payload.get("kind") == StaffRole.Kind.INSPECTOR:
            _save(draft, "office_user_region", payload)
            items = list(Region.objects.filter(governorate_id=payload["governorate"]).order_by("name"))
            rows = [[{"text": item.name[:40], "callback_data": f"un:{item.pk}"}] for item in items[:8]]
            rows.append([{"text": "القائمة", "callback_data": "mn"}])
            _say(chat_id, "اختر المنطقة.", markup={"inline_keyboard": rows})
            return
        _save(draft, "office_user_name", payload)
        _say(chat_id, "أرسل اسم الدخول.")
        return
    payload["region"] = int(raw)
    _save(draft, "office_user_name", payload)
    _say(chat_id, "أرسل اسم الدخول.")


def _create_user(chat_id, actor, draft, payload, password):
    if len(password) < 12:
        _say(chat_id, "كلمة المرور يجب أن تكون 12 محرفاً على الأقل.")
        return
    role = StaffRole.objects.filter(pk=payload.get("role_id")).first()
    if role is None:
        _say(chat_id, "الدور غير موجود.")
        return
    try:
        created = User(
            username=payload.get("username") or "",
            role=role.kind,
            staff_role=role,
            governorate_id=payload.get("governorate"),
            region_id=payload.get("region"),
        )
        created.set_password(password)
        created.full_clean()
        created.save()
    except (ValidationError, IntegrityError) as error:
        _say(chat_id, error.messages[0] if isinstance(error, ValidationError) else "اسم الدخول مستخدم.")
        return
    draft.delete()
    _say(chat_id, f"تم إنشاء المستخدم {created.username}.")


def _governorates(chat_id, user, page):
    if user is None or not allows(user, "can_manage_geography"):
        _say(chat_id, "غير مسموح.")
        return
    items = list(Governorate.objects.order_by("name"))
    chunk = items[page * 6:(page + 1) * 6]
    rows = [[{"text": item.name[:40], "callback_data": "gv:0"}] for item in chunk]
    rows.append([{"text": "إضافة محافظة", "callback_data": "ga"}, {"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "المحافظات.", markup={"inline_keyboard": rows or [[{"text": "إضافة محافظة", "callback_data": "ga"}]]})


def _region_governorates(chat_id, user, page):
    if user is None or not allows(user, "can_manage_geography"):
        _say(chat_id, "غير مسموح.")
        return
    items = list(Governorate.objects.order_by("name"))
    chunk = items[page * 6:(page + 1) * 6]
    rows = [[{"text": item.name[:40], "callback_data": f"rgg:{item.pk}"}] for item in chunk]
    rows.append([{"text": "القائمة", "callback_data": "mn"}])
    _say(chat_id, "اختر المحافظة لإضافة منطقة.", markup={"inline_keyboard": rows})


def _ask_region_name(chat_id, user, governorate_id):
    if user is None or not allows(user, "can_manage_geography"):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    _save(draft, "office_region_name", {"governorate": governorate_id})
    _say(chat_id, "أرسل اسم المنطقة.")


def _ask(chat_id, user, step, text):
    if user is None or not allows(user, "can_manage_geography"):
        _say(chat_id, "غير مسموح.")
        return
    draft = _draft(chat_id)
    _save(draft, step, {})
    _say(chat_id, text)


def _settings(chat_id, user):
    if user is None or not allows(user, "can_manage_settings"):
        _say(chat_id, "غير مسموح.")
        return
    row = SystemSettings.current()
    status = TelegramWebhookStatus.current()
    state = "مفعّلة" if row.web_complaints_enabled else "متوقفة"
    hook = "مربوط" if status.registered else "غير مربوط"
    _say(
        chat_id,
        f"شكاوى الموقع: {state}\nحالة تلغرام: {hook}",
        markup={"inline_keyboard": [
            [{"text": "إيقاف الشكاوى" if row.web_complaints_enabled else "تفعيل الشكاوى", "callback_data": "sw"}],
            [{"text": "القائمة", "callback_data": "mn"}],
        ]},
    )


def _toggle_web_complaints(chat_id, user):
    if user is None or not allows(user, "can_manage_settings"):
        _say(chat_id, "غير مسموح.")
        return
    row = SystemSettings.current()
    row.web_complaints_enabled = not row.web_complaints_enabled
    row.save(update_fields=["web_complaints_enabled"])
    _settings(chat_id, user)


def _image(downloaded):
    image = ContentFile(base64.b64decode(downloaded["image"]), name=downloaded["image_name"])
    name = (image.name or "").lower()
    image.content_type = "image/png" if name.endswith(".png") else "image/webp" if name.endswith(".webp") else "image/jpeg"
    return image
