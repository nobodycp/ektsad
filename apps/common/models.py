from django.db import models


class SystemSettings(models.Model):
    web_complaints_enabled = models.BooleanField(default=True)
    telegram_bot_token = models.CharField(max_length=256, blank=True)
    telegram_bot_username = models.CharField(max_length=64, blank=True)
    telegram_webhook_secret = models.CharField(max_length=256, blank=True)

    @classmethod
    def current(cls):
        row, _created = cls.objects.get_or_create(pk=1)
        return row
