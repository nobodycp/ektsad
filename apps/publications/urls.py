from django.urls import path

from apps.publications.api import (
    crossing_detail,
    crossings,
    latest_crossing,
    latest_crossing_media,
    latest_price,
    latest_price_media,
    price_detail,
    prices,
)


urlpatterns = [
    path("prices/", prices),
    path("prices/latest/", latest_price),
    path("prices/<int:pk>/", price_detail),
    path("crossings/", crossings),
    path("crossings/<int:pk>/", crossing_detail),
    path("crossings/latest/", latest_crossing),
    path("media/prices/latest/", latest_price_media),
    path("media/crossings/latest/", latest_crossing_media),
]
