from django.db import connection
from django.http import HttpResponse, HttpResponseServerError
from django.urls import include, path, re_path

from apps.accounts.api import login_view, logout_view, me_view, return_session, user_detail
from apps.common.api import public_settings, system_settings
from apps.complaints.api import (
    assign, complaint_actions, complaint_detail, complaint_media, complaint_notices, complaints, field_report,
    followup_media, legal_close, public_complaint, return_to_governor,
)
from apps.geography.api import (
    governorate_detail, governorates, public_governorates, public_regions, region_detail, regions,
)
from config.spa import spa

def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        return HttpResponseServerError()
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("health/", health),
    path("api/auth/login/", login_view),
    path("api/auth/logout/", logout_view),
    path("api/auth/return/", return_session),
    path("api/auth/me/", me_view),
    path("api/settings/public/", public_settings),
    path("api/system-settings/", system_settings),
    path("api/users/<int:pk>/", user_detail),
    path("api/governorates/public/", public_governorates),
    path("api/regions/public/", public_regions),
    path("api/governorates/<int:pk>/", governorate_detail),
    path("api/regions/<int:pk>/", region_detail),
    path("api/governorates/", governorates),
    path("api/regions/", regions),
    path("api/complaints/", complaints),
    path("api/complaints/notices/", complaint_notices),
    path("api/complaints/public/", public_complaint),
    path("api/complaints/actions/", complaint_actions),
    path("api/complaints/<int:pk>/", complaint_detail),
    path("api/complaints/<int:pk>/assign/", assign),
    path("api/complaints/<int:pk>/return/", return_to_governor),
    path("api/complaints/<int:pk>/field-report/", field_report),
    path("api/complaints/<int:pk>/legal-close/", legal_close),
    path("api/media/complaints/<int:pk>/", complaint_media),
    path("api/media/followups/<int:pk>/<int:file_id>/", followup_media),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.field_missions.urls")),
    path("api/", include("apps.publications.urls")),
    path("api/", include("apps.reports.urls")),
    path("api/", include("apps.telegram.urls")),
    re_path(r"^(?P<resource>.*)$", spa),
]
