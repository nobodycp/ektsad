from django.db import connection
from django.http import HttpResponse, HttpResponseServerError
from django.urls import path

from apps.accounts.api import login_view, logout_view, me_view, user_detail
from apps.complaints.api import (
    assign, complaint_actions, complaint_detail, complaints, field_report, legal_close,
)
from apps.geography.api import governorates, regions

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
    path("api/auth/me/", me_view),
    path("api/users/<int:pk>/", user_detail),
    path("api/governorates/", governorates),
    path("api/regions/", regions),
    path("api/complaints/", complaints),
    path("api/complaints/actions/", complaint_actions),
    path("api/complaints/<int:pk>/", complaint_detail),
    path("api/complaints/<int:pk>/assign/", assign),
    path("api/complaints/<int:pk>/field-report/", field_report),
    path("api/complaints/<int:pk>/legal-close/", legal_close),
]
