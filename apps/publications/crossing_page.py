"""Public page opened by the sheet's QR code. The sheet only, no site chrome."""

from datetime import date

from django.http import FileResponse, Http404, HttpResponse

from apps.publications.models import CrossingReport

PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>حركة الشاحنات الواردة من المعابر</title>
<style>
  html, body { margin: 0; background: #fbf9f4; }
  img { display: block; width: min(720px, 100%); height: auto; margin: 0 auto; }
</style>
</head>
<body>
<img src="sheet.png" alt="حركة الشاحنات الواردة من المعابر">
</body>
</html>
"""


def _report(year, month, day):
    try:
        movement = date(int(year), int(month), int(day))
    except ValueError:
        raise Http404
    report = CrossingReport.objects.filter(movement_date=movement).first()
    if report is None or not report.image:
        raise Http404
    return report


def crossing_page(request, year, month, day):
    _report(year, month, day)
    return HttpResponse(PAGE)


def crossing_sheet_file(request, year, month, day):
    report = _report(year, month, day)
    return FileResponse(report.image.open("rb"), content_type="image/png")
