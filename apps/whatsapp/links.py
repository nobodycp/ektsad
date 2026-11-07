from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import allows
from apps.whatsapp.models import WhatsAppLink


def digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def find_link(phone):
    number = digits(phone)
    if not number:
        return None
    row = WhatsAppLink.objects.select_related("user", "user__staff_role").filter(phone=number).first()
    if row is not None:
        return row
    if len(number) < 9:
        return None
    return WhatsAppLink.objects.select_related("user", "user__staff_role").filter(phone__endswith=number[-9:]).first()


@require_http_methods(["POST", "DELETE"])
def user_whatsapp_link(request, pk):
    if not allows(request.user, "can_manage_users"):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    user = User.objects.filter(pk=pk).first()
    if user is None:
        return JsonResponse({"detail": "غير موجود."}, status=404)
    if request.method == "DELETE":
        WhatsAppLink.objects.filter(user=user).delete()
        return JsonResponse({}, status=204)
    import json
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "بيانات غير صالحة."}, status=400)
    number = digits(payload.get("phone"))
    if len(number) < 9:
        return JsonResponse({"detail": "اكتب رقم واتساب مع مقدمة الدولة."}, status=400)
    tail = number[-9:]
    clash = WhatsAppLink.objects.exclude(user=user).filter(phone__endswith=tail)
    if clash.exists():
        return JsonResponse({"detail": "هذا الرقم مربوط بحساب آخر."}, status=400)
    try:
        with transaction.atomic():
            WhatsAppLink.objects.filter(user=user).delete()
            WhatsAppLink.objects.create(user=user, phone=number)
    except IntegrityError:
        return JsonResponse({"detail": "هذا الرقم مربوط بحساب آخر."}, status=400)
    return JsonResponse({"phone": number})
