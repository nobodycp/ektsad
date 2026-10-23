from django.db import models


class PriceReport(models.Model):
    image = models.ImageField(upload_to="prices/")
    published_at = models.DateTimeField(auto_now_add=True)
    publisher = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="price_reports"
    )
    publisher_name = models.CharField(max_length=255, blank=True)


class CrossingReport(models.Model):
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="crossings/", null=True, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    publisher = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="crossing_reports"
    )
    publisher_name = models.CharField(max_length=255, blank=True)
