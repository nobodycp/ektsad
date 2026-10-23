from django.db import connection
from django.http import HttpResponse, HttpResponseServerError
from django.urls import path


def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        return HttpResponseServerError()
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [path("health/", health)]
