from django.core.management.base import BaseCommand

from apps.telegram.webhook import register_webhook


class Command(BaseCommand):
    help = "Register the Telegram webhook. Failure is recorded and does not stop boot."

    def handle(self, *args, **options):
        register_webhook()
