import time

from django.core.management.base import BaseCommand

from apps.telegram.outbox import send_telegram_outbox


class Command(BaseCommand):
    help = "Keep sending due Telegram outbox messages."

    def handle(self, *args, **options):
        while True:
            send_telegram_outbox()
            time.sleep(15)
