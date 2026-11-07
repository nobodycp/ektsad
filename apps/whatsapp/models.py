from django.conf import settings
from django.db import models


class WhatsAppLink(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="whatsapp_link")
    phone = models.CharField(max_length=32, unique=True)
    linked_at = models.DateTimeField(auto_now_add=True)


class WhatsAppSession(models.Model):
    phone = models.CharField(max_length=32, unique=True)
    step = models.CharField(max_length=32, blank=True)
    payload = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class WhatsAppInbound(models.Model):
    message_id = models.CharField(max_length=512, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)
