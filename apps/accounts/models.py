from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.geography.models import Governorate, Region


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        GOVERNOR = "governor", "Governor"
        INSPECTOR = "inspector", "Inspector"
        LEGAL = "legal", "Legal"

    display_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices)
    governorate = models.ForeignKey(
        Governorate, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    region = models.ForeignKey(
        Region, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    can_publish_prices = models.BooleanField(default=False)
    can_publish_crossings = models.BooleanField(default=False)
    can_view_all_complaints = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        no_geography_roles = {self.Role.ADMIN, self.Role.LEGAL}
        if self.role in no_geography_roles and (self.governorate_id or self.region_id):
            raise ValidationError("هذا الدور لا يرتبط بنطاق جغرافي.")
        if self.role == self.Role.GOVERNOR and not self.governorate_id:
            raise ValidationError("المحافظة مطلوبة.")
        if self.role == self.Role.GOVERNOR and self.region_id:
            raise ValidationError("مدير المحافظة لا يرتبط بمنطقة.")
        if self.role == self.Role.INSPECTOR:
            if not self.governorate_id or not self.region_id:
                raise ValidationError("المحافظة والمنطقة مطلوبتان.")
            if self.region.governorate_id != self.governorate_id:
                raise ValidationError("المنطقة لا تتبع المحافظة.")
