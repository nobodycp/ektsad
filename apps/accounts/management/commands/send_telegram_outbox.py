from django.core.management.base import BaseCommand

from apps.telegram.outbox import send_telegram_outbox


class Command(BaseCommand):
    help = "Send due Telegram outbox messages once."

    def handle(self, *args, **options):
        self.stdout.write(str(send_telegram_outbox()))
