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

    kind = models.CharField(max_length=32, choices=Kind.choices)
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
