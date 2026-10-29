from django.http import HttpResponse

MAP_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تحديد الموقع</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html, body { height: 100%; margin: 0; }
  body { display: flex; flex-direction: column; font-family: sans-serif; }
  p { margin: 0; padding: 12px 16px; }
  #map { flex: 1; min-height: 240px; }
</style>
</head>
<body>
<p>اضغط مكان الشكوى على الخريطة، ثم اضغط تأكيد.</p>
<div id="map"></div>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const map = L.map("map").setView([31.5, 34.47], 8);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);
let marker = null;
let point = null;
map.on("click", (event) => {
  point = event.latlng;
  if (marker) marker.setLatLng(point);
  else marker = L.marker(point).addTo(map);
  if (tg) tg.MainButton.setText("تأكيد").show();
});
if (tg) {
  tg.MainButton.onClick(() => {
    if (!point) return;
    tg.sendData(JSON.stringify({ latitude: point.lat, longitude: point.lng }));
  });
}
</script>
</body>
</html>
"""


def map_page(request):
    return HttpResponse(MAP_PAGE)
