from django.db import models


class WhatsAppSession(models.Model):
    phone = models.CharField(max_length=32, unique=True)
    step = models.CharField(max_length=32, blank=True)
    payload = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class WhatsAppInbound(models.Model):
    message_id = models.CharField(max_length=512, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)
