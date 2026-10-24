import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


ADMIN_ACCOUNT = ("admin", "admin-password-12", "مدير النظام", User.Role.ADMIN)
REQUIRED_KEYS = (
    "DJANGO_SECRET_KEY",
    "ALLOWED_HOSTS",
    "BEHIND_PROXY",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


class Command(BaseCommand):
    help = "Ensure the main admin account exists."

    def handle(self, *args, **options):
        self._validate_environment()
        self._ensure_admin()

    def _validate_environment(self):
        keys = list(REQUIRED_KEYS)
        if os.environ.get("BEHIND_PROXY") == "1":
            keys.append("CSRF_TRUSTED_ORIGINS")
        for key in keys:
            if not os.environ.get(key):
                raise CommandError(f"Missing required environment variable: {key}")

    def _ensure_admin(self):
        username, password, display_name, role = ADMIN_ACCOUNT
        if User.objects.filter(username=username).exists():
            return
        user = User(username=username, display_name=display_name, role=role)
        user.set_password(password)
        user.full_clean()
        user.save()
