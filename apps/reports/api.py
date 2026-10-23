from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.geography.models import Governorate
from apps.reports.queries import _date_value, _today, governor_daily, admin_report


def _forbidden(request):
    return not request.user.is_authenticated


@require_GET
def governor_report(request):
    if _forbidden(request) or request.user.role not in {User.Role.GOVERNOR, User.Role.ADMIN}:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.user.role == User.Role.GOVERNOR:
        governorate = request.user.governorate
    else:
        governorate_id = request.GET.get("governorate")
        if not governorate_id:
            return JsonResponse({"detail": "المحافظة مطلوبة."}, status=400)
        governorate = Governorate.objects.filter(pk=governorate_id).first()
        if governorate is None:
            return JsonResponse({"detail": "المحافظة غير صالحة."}, status=400)
    try:
        day = _date_value(request.GET.get("date"), _today())
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
    return JsonResponse(governor_daily(governorate, day))


@require_GET
def reports(request):
    if _forbidden(request) or request.user.role != User.Role.ADMIN:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        return JsonResponse(admin_report(request.GET))
    except ValidationError as error:
        return JsonResponse({"detail": error.messages[0]}, status=400)
