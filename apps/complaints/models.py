from django.core.exceptions import ValidationError
from django.db import models


class Complaint(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "واردة", "واردة"
        FIELD = "قيد المتابعة الميدانية", "قيد المتابعة الميدانية"
        FINISHED = "منتهية", "منتهية"
        LEGAL = "قيد المتابعة في الشؤون القانونية", "قيد المتابعة في الشؤون القانونية"
        RESOLVED = "تم المعالجه خلص", "تم المعالجه خلص"

    class Source(models.TextChoices):
        WEB = "web", "Web"
        TELEGRAM = "telegram", "Telegram"

    governorate = models.ForeignKey("geography.Governorate", on_delete=models.PROTECT)
    region = models.ForeignKey("geography.Region", on_delete=models.PROTECT)
    title = models.CharField(max_length=255)
    body = models.TextField()
    image = models.ImageField(upload_to="complaints/", null=True, blank=True)
    status = models.CharField(max_length=64, choices=Status.choices, default=Status.RECEIVED)
    inspector = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_complaints")
    inspector_name = models.CharField(max_length=255, blank=True)
    assigned_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="complaints_assigned")
    assigned_by_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    legal_referred_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    submitter_ip = models.GenericIPAddressField(null=True, blank=True)
    telegram_chat_id = models.CharField(max_length=255, blank=True)
    telegram_user_id = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.WEB)
    accept_ip = models.GenericIPAddressField(null=True, blank=True)
    accept_channel = models.CharField(max_length=16, choices=Source.choices, blank=True)
    is_flagged = models.BooleanField(default=False)
    flagged_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="flagged_complaints")
    flagged_at = models.DateTimeField(null=True, blank=True)


class FollowUp(models.Model):
    class Place(models.TextChoices):
        FIELD = "field", "Field"
        LEGAL = "legal", "Legal"

    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="follow_ups")
    author = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    author_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    place = models.CharField(max_length=16, choices=Place.choices)
    body = models.TextField()
    author_ip = models.GenericIPAddressField(null=True, blank=True)
    author_telegram_id = models.CharField(max_length=255, blank=True)
    channel = models.CharField(max_length=16, choices=Complaint.Source.choices, default=Complaint.Source.WEB)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("لا يمكن تعديل المتابعة.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يمكن حذف المتابعة.")


class FollowUpFile(models.Model):
    follow_up = models.ForeignKey(FollowUp, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="complaint-followups/")


class ComplaintSeen(models.Model):
    """A staff member opened this complaint. Other accounts stay unread."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="seen_complaints")
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="seen_by")
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "complaint"), name="unique_complaint_seen")
        ]
