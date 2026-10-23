from django.urls import path

from apps.publications.api import (
    crossings,
    latest_crossing,
    latest_crossing_media,
    latest_price,
    latest_price_media,
    prices,
)


urlpatterns = [
    path("prices/", prices),
    path("prices/latest/", latest_price),
    path("crossings/", crossings),
    path("crossings/latest/", latest_crossing),
    path("media/prices/latest/", latest_price_media),
    path("media/crossings/latest/", latest_crossing_media),
]
