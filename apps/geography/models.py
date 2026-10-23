from django.db import models


class Governorate(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Region(models.Model):
    governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, related_name="regions"
    )
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("governorate", "name"), name="unique_region_per_governorate"
            )
        ]

    def __str__(self):
        return self.name
