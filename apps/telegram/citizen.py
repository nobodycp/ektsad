"""Citizen complaint steps: kind, place, confirmation, and an optional map pin."""

WELCOME = "أهلاً وسهلاً بك عزيز المواطن. يرجى اتباع الخطوات التالية حتى يتم تقديم الشكوى بنجاح."
KIND_PROMPT = "عزيزي المواطن، يرجى اختيار نوع الشكوى."
KIND_TEXT_PROMPT = "اكتب نوع الشكوى."
RESUME_PROMPT = "تكمل الشكوى الحالية أم تبدأ من جديد؟"
LOCATION_PROMPT = (
    "أرسل موقع الشكوى إن رغبت.\n"
    "اضغط أخذ الموقع الآن لموقع هاتفك، أو حدد نقطة على الخريطة.\n"
    "أو اضغط تخطي."
)
COMPLAINT_STEPS = {"kind", "kind_text", "governorate", "region", "title", "body", "image", "location", "confirm"}
FIXED_KINDS = {
    "k:price": "غلاء أسعار",
    "k:monopoly": "احتكار",
    "k:expiry": "انتهاء صلاحية",
}
KIND_LIMIT = 40
BUTTON_STYLES = {"danger", "primary", "success"}


def total_for(payload):
    return 9 if (payload or {}).get("kind_mode") == "other" else 8


def step_number(step, payload):
    other = (payload or {}).get("kind_mode") == "other"
    return {
        "kind": 1,
        "kind_text": 2,
        "governorate": 3 if other else 2,
        "region": 4 if other else 3,
        "title": 5 if other else 4,
        "body": 6 if other else 5,
        "image": 7 if other else 6,
        "location": 8 if other else 7,
        "confirm": 9 if other else 8,
    }[step]


def stepped(step, payload, body):
    return f"الخطوة {step_number(step, payload)} من {total_for(payload)}\n{body}"


def map_page_url(base):
    base = (base or "").rstrip("/")
    if not base.startswith("https://"):
        return ""
    return f"{base}/telegram/map/"


def map_link(latitude, longitude):
    return f"https://maps.google.com/maps?q={latitude},{longitude}"


def parse_point(latitude, longitude):
    try:
        lat = round(float(latitude), 6)
        lng = round(float(longitude), 6)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def confirmation(payload, governorate_name, region_name):
    located = "تم إرفاقه" if payload.get("latitude") is not None else "بدون موقع"
    body = (
        "تأكيد الشكوى\n"
        f"النوع: {payload.get('kind', '')}\n"
        f"المحافظة: {governorate_name}\n"
        f"المنطقة: {region_name}\n"
        f"العنوان: {payload.get('title', '')}\n"
        f"النص: {payload.get('body', '')}\n"
        f"الموقع: {located}"
    )
    return stepped("confirm", payload, body)


def receipt(pk):
    return f"تم استلام الشكوى.\nرقم الشكوى: {pk}"


def kind_rows():
    return [
        [
            {"text": "غلاء أسعار", "callback_data": "k:price"},
            {"text": "احتكار", "callback_data": "k:monopoly"},
        ],
        [
            {"text": "انتهاء صلاحية", "callback_data": "k:expiry"},
            {"text": "أخرى", "callback_data": "k:other"},
        ],
    ]


def location_rows(map_url):
    rows = [[{"text": "أخذ الموقع الآن", "request_location": True}]]
    if map_url:
        rows.append([{"text": "تحديد موقع على الخريطة", "web_app": {"url": map_url}}])
    rows.append([{"text": "تخطي", "callback_data": "locskip"}])
    return rows


def resume_rows():
    return [[
        {"text": "تكمل", "callback_data": "resume"},
        {"text": "أبدأ من جديد", "callback_data": "restart"},
    ]]
