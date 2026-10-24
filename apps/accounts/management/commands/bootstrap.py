import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.geography.models import Governorate, Region


TRIAL_GOVERNORATE = "محافظة تجريبية"
TRIAL_REGIONS = ("المنطقة الأولى", "المنطقة الثانية")
DEMO_USERS = (
    ("admin", "admin-password-12", "مدير النظام", User.Role.ADMIN),
    ("governor", "governor-password-12", "مدير المحافظة", User.Role.GOVERNOR),
    ("inspector", "inspector-password-12", "المفتش", User.Role.INSPECTOR),
    ("legal", "legal-password-12", "الشؤون القانونية", User.Role.LEGAL),
)
REQUIRED_KEYS = (
    "DJANGO_SECRET_KEY",
    "ALLOWED_HOSTS",
    "BEHIND_PROXY",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


class Command(BaseCommand):
    help = "Create trial geography and initial staff accounts."

    def handle(self, *args, **options):
        self._validate_environment()
        self._ensure_trial_geography()
        self._ensure_users()

    def _validate_environment(self):
        keys = list(REQUIRED_KEYS)
        if os.environ.get("BEHIND_PROXY") == "1":
            keys.append("CSRF_TRUSTED_ORIGINS")
        for key in keys:
            if not os.environ.get(key):
                raise CommandError(f"Missing required environment variable: {key}")

    def _ensure_trial_geography(self):
        if Governorate.objects.exists():
            return
        governorate = Governorate.objects.create(name=TRIAL_GOVERNORATE)
        for name in TRIAL_REGIONS:
            Region.objects.get_or_create(governorate=governorate, name=name)

    def _ensure_users(self):
        governorate = Governorate.objects.filter(name=TRIAL_GOVERNORATE).first()
        for username, password, display_name, role in DEMO_USERS:
            if User.objects.filter(username=username).exists():
                continue
            fields = {
                "username": username,
                "display_name": display_name,
                "role": role,
            }
            if role in {User.Role.GOVERNOR, User.Role.INSPECTOR}:
                if governorate is None:
                    raise CommandError(f"Missing required geography: {TRIAL_GOVERNORATE}")
                fields["governorate"] = governorate
            if role == User.Role.INSPECTOR:
                region = Region.objects.filter(
                    governorate=governorate, name=TRIAL_REGIONS[0]
                ).first()
                if region is None:
                    raise CommandError(f"Missing required geography: {TRIAL_REGIONS[0]}")
                fields["region"] = region
            user = User(**fields)
            user.set_password(password)
            user.full_clean()
            user.save()
