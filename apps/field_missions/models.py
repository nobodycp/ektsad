from django.core.exceptions import ValidationError
from django.db import models


class FieldMission(models.Model):
    class Kind(models.TextChoices):
        SEIZURE = "ضبط", "ضبط"
        HOLD = "تحفظ", "تحفظ"
        STATUS = "إثبات حالة", "إثبات حالة"
        CONFISCATION = "مصادرة", "مصادرة"
        DESTRUCTION = "إتلاف", "إتلاف"
        SAMPLES = "عينات فحص", "عينات فحص"
        OTHER = "أخرى", "أخرى"

    class Priority(models.TextChoices):
        DANGER = "خطر", "خطر"
        URGENT = "عاجل", "عاجل"
        MEDIUM = "متوسط", "متوسط"
        NORMAL = "عادي", "عادي"

    class Status(models.TextChoices):
        OFFICE = "عند إدارة المحافظة", "عند إدارة المحافظة"
        FIELD = "قيد المتابعة الميدانية", "قيد المتابعة الميدانية"
        FINISHED = "منتهية", "منتهية"
        LEGAL = "قيد المتابعة في الشؤون القانونية", "قيد المتابعة في الشؤون القانونية"
        RESOLVED = "تم المعالجة", "تم المعالجة"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=64, choices=Status.choices, default=Status.FIELD)
    details = models.TextField()
    place_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    image = models.ImageField(upload_to="field-missions/", null=True, blank=True)
    governorate = models.ForeignKey("geography.Governorate", on_delete=models.PROTECT)
    region = models.ForeignKey("geography.Region", null=True, blank=True, on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="opened_field_missions"
    )
    created_by_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    field_replied_at = models.DateTimeField(null=True, blank=True)
    legal_referred_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)


class FieldMissionAssignee(models.Model):
    mission = models.ForeignKey(FieldMission, on_delete=models.CASCADE, related_name="assignees")
    user = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="field_mission_duties"
    )
    display_name = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("mission", "user"), name="unique_field_mission_assignee")
        ]


class FieldMissionFollowUp(models.Model):
    class Place(models.TextChoices):
        ROUTE = "route", "Route"
        FIELD = "field", "Field"
        LEGAL = "legal", "Legal"

    mission = models.ForeignKey(FieldMission, on_delete=models.CASCADE, related_name="follow_ups")
    author = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    author_name = models.CharField(max_length=255, blank=True)
    place = models.CharField(max_length=16, choices=Place.choices)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("لا يمكن تعديل المتابعة.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يمكن حذف المتابعة.")


class FieldMissionFollowUpFile(models.Model):
    follow_up = models.ForeignKey(FieldMissionFollowUp, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="field-mission-followups/")
