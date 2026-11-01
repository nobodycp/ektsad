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
    movement_date = models.DateField(null=True, blank=True, unique=True)
    weekday = models.CharField(max_length=20, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    publisher = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="crossing_reports"
    )
    publisher_name = models.CharField(max_length=255, blank=True)


class CrossingGate(models.Model):
    report = models.ForeignKey(CrossingReport, related_name="gates", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    commercial = models.PositiveIntegerField(default=0)
    aid = models.PositiveIntegerField(default=0)
    position = models.PositiveSmallIntegerField(default=0)


class CrossingFuel(models.Model):
    report = models.ForeignKey(CrossingReport, related_name="fuels", on_delete=models.CASCADE)
    gate = models.CharField(max_length=80)
    party = models.CharField(max_length=20)
    kind = models.CharField(max_length=20)
    count = models.PositiveIntegerField(default=0)


class CrossingLoad(models.Model):
    report = models.ForeignKey(CrossingReport, related_name="loads", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    count = models.PositiveIntegerField(default=0)
    position = models.PositiveSmallIntegerField(default=0)


class CrossingAidLine(models.Model):
    report = models.ForeignKey(CrossingReport, related_name="aid_lines", on_delete=models.CASCADE)
    organization = models.CharField(max_length=120)
    item = models.CharField(max_length=80)
    count = models.PositiveIntegerField(default=0)
    position = models.PositiveSmallIntegerField(default=0)
