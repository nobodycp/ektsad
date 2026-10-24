from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse


def spa(request, resource=""):
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Not found"}, status=404)
    dist = Path(settings.SPA_DIST).resolve()
    relative = Path(resource)
    if resource and not relative.is_absolute():
        candidate = (dist / relative).resolve()
        if (candidate == dist or dist in candidate.parents) and candidate.is_file():
            return FileResponse(candidate.open("rb"))
    index = dist / "index.html"
    if not index.is_file():
        return HttpResponse("الواجهة غير مبنية.", status=503, content_type="text/plain; charset=utf-8")
    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
