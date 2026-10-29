import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import allows
from apps.telegram.models import BotButton

ACTIONS = (
    ("nw", "تقديم شكوى"),
    ("cr", "حركة المعابر"),
    ("pr", "القائمة الاسترشادية"),
    ("ls:a:0", "الشكاوى"),
    ("ms:0", "المهمات"),
    ("mc", "إنشاء مهمة"),
    ("prb", "نشر الأسعار"),
    ("crb", "نشر المعابر"),
    ("rp", "التقارير"),
    ("us:0", "المستخدمون"),
    ("gv:0", "المحافظات"),
    ("rg:0", "المناطق"),
    ("st", "إعدادات النظام"),
)

AUDIENCES = (
    ("everyone", "الجميع"),
    ("linked", "الحسابات المربوطة"),
    ("can_view_field_missions", "من يرى المهمات"),
    ("can_open_field_missions", "من ينشئ مهمات"),
    ("can_publish", "من ينشر"),
    ("reports", "من يرى التقارير"),
    ("can_manage_users", "من يدير المستخدمين"),
    ("can_manage_geography", "من يدير المحافظات"),
    ("can_manage_settings", "من يدير الإعدادات"),
)

DEFAULTS = (
    (1, 1, "تقديم شكوى", "nw", "everyone", "danger"),
    (2, 1, "القائمة الاسترشادية", "pr", "everyone", "primary"),
    (3, 1, "حركة المعابر", "cr", "everyone", "success"),
    (4, 1, "الشكاوى", "ls:a:0", "linked", ""),
    (5, 1, "المهمات", "ms:0", "can_view_field_missions", ""),
    (5, 2, "إنشاء مهمة", "mc", "can_open_field_missions", ""),
    (6, 1, "نشر الأسعار", "prb", "can_publish", ""),
    (6, 2, "نشر المعابر", "crb", "can_publish", ""),
    (7, 1, "التقارير", "rp", "reports", ""),
    (8, 1, "المستخدمون", "us:0", "can_manage_users", ""),
    (9, 1, "المحافظات", "gv:0", "can_manage_geography", ""),
    (9, 2, "المناطق", "rg:0", "can_manage_geography", ""),
    (10, 1, "إعدادات النظام", "st", "can_manage_settings", ""),
)

STYLES = (
    ("", "بلا لون"),
    ("danger", "أحمر"),
    ("primary", "أزرق"),
    ("success", "أخضر"),
)

ACTION_LABELS = dict(ACTIONS)
AUDIENCE_LABELS = dict(AUDIENCES)
STYLE_LABELS = dict(STYLES)


def seed_buttons():
    if BotButton.objects.exists():
        return
    BotButton.objects.bulk_create([
        BotButton(row=row, position=position, label=label, target=target, audience=audience, style=style)
        for row, position, label, target, audience, style in DEFAULTS
    ])


def shown(user, button):
    if button.audience == "everyone":
        return True
    if user is None or not getattr(user, "is_active", False):
        return False
    if button.audience == "linked":
        return True
    if button.audience == "reports":
        from apps.telegram.office import _bot_reports
        return _bot_reports(user)
    if button.audience == "can_open_field_missions":
        return user.role != User.Role.LEGAL and allows(user, "can_open_field_missions")
    return allows(user, button.audience)


def _menu_button(label, target, style):
    item = {"text": label[:64], "callback_data": target}
    if style in STYLE_LABELS and style:
        item["style"] = style
    return item


def rows_for(user):
    if not BotButton.objects.exists():
        return _builtin_rows(user)
    grouped = []
    current = None
    bucket = []
    for button in BotButton.objects.filter(enabled=True):
        if not shown(user, button):
            continue
        if current != button.row:
            if bucket:
                grouped.append(bucket)
            bucket = []
            current = button.row
        bucket.append(_menu_button(button.label, button.target, button.style))
    if bucket:
        grouped.append(bucket)
    return grouped


def _builtin_rows(user):
    rows = []
    current = None
    bucket = []
    for row, _position, label, target, audience, style in DEFAULTS:
        probe = BotButton(label=label, target=target, audience=audience, enabled=True)
        if not shown(user, probe):
            continue
        if current != row:
            if bucket:
                rows.append(bucket)
            bucket = []
            current = row
        bucket.append(_menu_button(label, target, style))
    if bucket:
        rows.append(bucket)
    return rows


def _payload(button):
    return {
        "id": button.pk,
        "label": button.label,
        "target": button.target,
        "target_label": ACTION_LABELS.get(button.target, button.target),
        "audience": button.audience,
        "audience_label": AUDIENCE_LABELS.get(button.audience, button.audience),
        "row": button.row,
        "position": button.position,
        "enabled": button.enabled,
        "style": button.style,
        "style_label": STYLE_LABELS.get(button.style, "بلا لون"),
    }


def _choices():
    return {
        "actions": [{"id": key, "label": label} for key, label in ACTIONS],
        "audiences": [{"id": key, "label": label} for key, label in AUDIENCES],
        "styles": [{"id": key, "label": label} for key, label in STYLES],
    }


def _body(request):
    if request.content_type == "application/json":
        return json.loads(request.body or "{}")
    return request.POST


def _can_edit(request):
    return request.user.is_authenticated and allows(request.user, "can_manage_settings")


def _number(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} رقم.")
    if number < 1 or number > 99:
        raise ValueError(f"{name} بين 1 و 99.")
    return number


def _clean(payload, current=None):
    label = str(payload.get("label", current.label if current else "")).strip()
    target = payload.get("target", current.target if current else "")
    audience = payload.get("audience", current.audience if current else "")
    enabled = payload.get("enabled", current.enabled if current else True)
    if isinstance(enabled, str):
        enabled = enabled not in {"0", "false", "False"}
    enabled = bool(enabled)
    if not label or len(label) > 64:
        raise ValueError("اسم الزر مطلوب، وبحد 64 حرفاً.")
    if label == "رجوع":
        raise ValueError("اسم رجوع محجوز للعودة.")
    if target not in ACTION_LABELS:
        raise ValueError("اختر زراً موجوداً للتوجيه إليه.")
    if audience not in AUDIENCE_LABELS:
        raise ValueError("اختر من يرى الزر.")
    style = str(payload.get("style", current.style if current else "") or "")
    if style not in STYLE_LABELS:
        raise ValueError("اختر لون الزر.")
    row = _number(payload.get("row", current.row if current else 1), "الصف")
    position = _number(payload.get("position", current.position if current else 1), "الترتيب")
    clash = BotButton.objects.filter(enabled=True, label=label)
    if current is not None:
        clash = clash.exclude(pk=current.pk)
    if enabled and clash.exists():
        raise ValueError("اسم الزر مستخدم في زر ظاهر.")
    return {
        "label": label,
        "target": target,
        "audience": audience,
        "row": row,
        "position": position,
        "enabled": enabled,
        "style": style,
    }


@require_http_methods(["GET", "POST"])
def buttons(request):
    if not _can_edit(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "GET":
        return JsonResponse({
            "results": [_payload(button) for button in BotButton.objects.all()],
            **_choices(),
        })
    try:
        fields = _clean(_body(request))
    except (ValueError, json.JSONDecodeError) as error:
        return JsonResponse({"detail": str(error) if isinstance(error, ValueError) else "بيانات غير صالحة."}, status=400)
    button = BotButton.objects.create(**fields)
    return JsonResponse(_payload(button), status=201)


@require_http_methods(["PATCH", "DELETE"])
def button_detail(request, pk):
    if not _can_edit(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    button = BotButton.objects.filter(pk=pk).first()
    if button is None:
        return JsonResponse({"detail": "الزر غير موجود."}, status=404)
    if request.method == "DELETE":
        button.delete()
        return JsonResponse({}, status=204)
    try:
        fields = _clean(_body(request), button)
    except (ValueError, json.JSONDecodeError) as error:
        return JsonResponse({"detail": str(error) if isinstance(error, ValueError) else "بيانات غير صالحة."}, status=400)
    for key, value in fields.items():
        setattr(button, key, value)
    button.save()
    return JsonResponse(_payload(button))
