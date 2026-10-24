import json

from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_http_methods

from apps.common.listing import paginate
from apps.field_missions.services import MissionError, may_view, open_mission, visible_missions


def _payload(request):
    if request.content_type and "multipart/form-data" in request.content_type:
        return request.POST
    if request.content_type and "application/json" in request.content_type:
        return json.loads(request.body or "{}")
    return request.POST


def _mission_data(mission):
    return {
        "id": mission.pk,
        "kind": mission.kind,
        "details": mission.details,
        "place_name": mission.place_name,
        "phone": mission.phone,
        "has_image": bool(mission.image),
        "governorate": mission.governorate_id,
        "governorate_name": mission.governorate.name,
        "region": mission.region_id,
        "region_name": mission.region.name if mission.region_id else None,
        "created_by_name": mission.created_by_name,
        "created_at": mission.created_at,
        "assignees": [
            {"id": row.user_id, "name": row.display_name}
            for row in mission.assignees.all()
        ],
    }


def _visible_or_none(request, pk):
    if not may_view(request.user):
        return None
    return (
        visible_missions(request.user)
        .select_related("governorate", "region")
        .prefetch_related("assignees")
        .filter(pk=pk)
        .first()
    )


@require_http_methods(["GET", "POST"])
def field_missions(request):
    if not request.user.is_authenticated or not may_view(request.user):
        if request.method == "POST" and request.user.is_authenticated:
            try:
                mission = open_mission(request.user, _payload(request), request.FILES.get("image"))
            except MissionError as error:
                return JsonResponse({"detail": error.message}, status=error.status)
            mission = _visible_or_none(request, mission.pk) or mission
            return JsonResponse(_mission_data(mission), status=201)
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "GET":
        queryset = visible_missions(request.user).select_related("governorate", "region").prefetch_related("assignees")
        kind = (request.GET.get("kind") or "").strip()
        if kind:
            queryset = queryset.filter(kind=kind)
        query = (request.GET.get("q") or "").strip()
        if query:
            queryset = queryset.filter(place_name__icontains=query)
        page = paginate(queryset.order_by("-created_at", "-pk"), request.GET)
        page["results"] = [_mission_data(mission) for mission in page["results"]]
        return JsonResponse(page)
    try:
        mission = open_mission(request.user, _payload(request), request.FILES.get("image"))
    except MissionError as error:
        return JsonResponse({"detail": error.message}, status=error.status)
    mission = (
        visible_missions(request.user)
        .select_related("governorate", "region")
        .prefetch_related("assignees")
        .get(pk=mission.pk)
    )
    return JsonResponse(_mission_data(mission), status=201)


@require_http_methods(["GET"])
def field_mission_media(request, pk):
    mission = _visible_or_none(request, pk)
    if mission is None or not mission.image:
        raise Http404
    return FileResponse(mission.image.open("rb"))
