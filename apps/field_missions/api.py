import json

from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_http_methods

from apps.common.listing import paginate
from apps.field_missions.services import (
    MissionError,
    close_mission,
    may_view,
    open_mission,
    redirect_mission,
    reply_mission,
    visible_missions,
)


def _payload(request):
    if request.content_type and "multipart/form-data" in request.content_type:
        return request.POST
    if request.content_type and "application/json" in request.content_type:
        return json.loads(request.body or "{}")
    return request.POST


def _mission_data(mission, *, detail=False):
    data = {
        "id": mission.pk,
        "kind": mission.kind,
        "priority": mission.priority,
        "status": mission.status,
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
        "field_replied_at": mission.field_replied_at,
        "legal_referred_at": mission.legal_referred_at,
        "closed_at": mission.closed_at,
        "assignees": [
            {"id": row.user_id, "name": row.display_name}
            for row in mission.assignees.all()
        ],
    }
    if detail:
        data["follow_ups"] = [
            {
                "id": line.pk,
                "author_name": line.author_name,
                "created_at": line.created_at,
                "place": line.place,
                "body": line.body,
                "files": [{"id": item.pk, "name": item.file.name} for item in line.files.all()],
            }
            for line in mission.follow_ups.order_by("created_at", "pk").prefetch_related("files")
        ]
    return data


def _visible_or_none(request, pk):
    if not may_view(request.user):
        return None
    return (
        visible_missions(request.user)
        .select_related("governorate", "region")
        .prefetch_related("assignees", "follow_ups__files")
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
def field_mission_detail(request, pk):
    mission = _visible_or_none(request, pk)
    if mission is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse(_mission_data(mission, detail=True))


def _act(request, pk, runner):
    mission = _visible_or_none(request, pk)
    if mission is None:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        runner(mission)
    except MissionError as error:
        return JsonResponse({"detail": error.message}, status=error.status)
    mission = _visible_or_none(request, pk)
    return JsonResponse(_mission_data(mission, detail=True))


@require_http_methods(["POST"])
def field_mission_redirect(request, pk):
    payload = _payload(request)

    def runner(mission):
        redirect_mission(request.user, mission, payload.get("inspector"))

    return _act(request, pk, runner)


@require_http_methods(["POST"])
def field_mission_reply(request, pk):
    def runner(mission):
        reply_mission(
            request.user,
            mission,
            request.POST.get("text", ""),
            request.FILES.getlist("files"),
            request.POST.get("destination"),
        )

    return _act(request, pk, runner)


@require_http_methods(["POST"])
def field_mission_close(request, pk):
    payload = _payload(request)

    def runner(mission):
        close_mission(request.user, mission, payload.get("notes", ""))

    return _act(request, pk, runner)


@require_http_methods(["GET"])
def field_mission_media(request, pk):
    mission = _visible_or_none(request, pk)
    if mission is None or not mission.image:
        raise Http404
    return FileResponse(mission.image.open("rb"))


@require_http_methods(["GET"])
def field_mission_followup_media(request, pk, file_id):
    mission = _visible_or_none(request, pk)
    if mission is None:
        raise Http404
    item = next(
        (row for line in mission.follow_ups.all() for row in line.files.all() if row.pk == file_id),
        None,
    )
    if item is None:
        raise Http404
    return FileResponse(item.file.open("rb"))
