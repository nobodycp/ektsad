from django.urls import path

from apps.field_missions.api import field_mission_media, field_missions


urlpatterns = [
    path("field-missions/", field_missions),
    path("media/field-missions/<int:pk>/", field_mission_media),
]
