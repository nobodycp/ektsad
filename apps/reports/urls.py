from django.urls import path

from apps.reports.api import governor_report, overview_report, reports


urlpatterns = [
    path("governor/report/", governor_report),
    path("reports/overview/", overview_report),
    path("reports/", reports),
]
