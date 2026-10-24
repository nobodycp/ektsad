from django.urls import path

from apps.field_missions.api import (
    field_mission_close,
    field_mission_detail,
    field_mission_followup_media,
    field_mission_media,
    field_mission_redirect,
    field_mission_reply,
    field_missions,
)


urlpatterns = [
    path("field-missions/", field_missions),
    path("field-missions/<int:pk>/", field_mission_detail),
    path("field-missions/<int:pk>/redirect/", field_mission_redirect),
    path("field-missions/<int:pk>/reply/", field_mission_reply),
    path("field-missions/<int:pk>/close/", field_mission_close),
    path("media/field-missions/<int:pk>/", field_mission_media),
    path("media/field-missions/<int:pk>/followups/<int:file_id>/", field_mission_followup_media),
]
