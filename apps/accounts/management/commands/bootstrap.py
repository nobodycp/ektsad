import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.geography.models import Governorate, Region


TRIAL_GOVERNORATE = "محافظة تجريبية"
TRIAL_REGIONS = ("المنطقة الأولى", "المنطقة الثانية")
USER_CONFIGS = (
    ("ADMIN", User.Role.ADMIN),
    ("GOVERNOR", User.Role.GOVERNOR),
    ("INSPECTOR", User.Role.INSPECTOR),
    ("LEGAL", User.Role.LEGAL),
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
        for prefix, _role in USER_CONFIGS:
            keys.extend(
                (f"{prefix}_USERNAME", f"{prefix}_PASSWORD", f"{prefix}_DISPLAY_NAME")
            )
        for key in keys:
            if not os.environ.get(key):
                raise CommandError(f"Missing required environment variable: {key}")
        for prefix, _role in USER_CONFIGS:
            key = f"{prefix}_PASSWORD"
            if len(os.environ[key]) < 12:
                raise CommandError(f"{key} must be at least 12 characters.")

    def _ensure_trial_geography(self):
        if Governorate.objects.exists():
            return
        governorate = Governorate.objects.create(name=TRIAL_GOVERNORATE)
        for name in TRIAL_REGIONS:
            Region.objects.get_or_create(governorate=governorate, name=name)

    def _ensure_users(self):
        governorate = Governorate.objects.filter(name=TRIAL_GOVERNORATE).first()
        for prefix, role in USER_CONFIGS:
            username = os.environ[f"{prefix}_USERNAME"]
            if User.objects.filter(username=username).exists():
                continue
            fields = {
                "username": username,
                "display_name": os.environ[f"{prefix}_DISPLAY_NAME"],
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
            user.set_password(os.environ[f"{prefix}_PASSWORD"])
            user.full_clean()
            user.save()
