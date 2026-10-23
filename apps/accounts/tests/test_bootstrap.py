import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.geography.models import Governorate, Region


ENV = {
    "DJANGO_SECRET_KEY": "test-secret",
    "ALLOWED_HOSTS": "localhost",
    "BEHIND_PROXY": "0",
    "POSTGRES_DB": "test",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test-password",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "admin-password-12",
    "ADMIN_DISPLAY_NAME": "مدير النظام",
    "GOVERNOR_USERNAME": "governor",
    "GOVERNOR_PASSWORD": "governor-password-12",
    "GOVERNOR_DISPLAY_NAME": "مدير المحافظة",
    "INSPECTOR_USERNAME": "inspector",
    "INSPECTOR_PASSWORD": "inspector-password-12",
    "INSPECTOR_DISPLAY_NAME": "المفتش",
    "LEGAL_USERNAME": "legal",
    "LEGAL_PASSWORD": "legal-password-12",
    "LEGAL_DISPLAY_NAME": "الشؤون القانونية",
}


class BootstrapTests(TestCase):
    @patch.dict(os.environ, ENV, clear=True)
    def test_bootstrap_seeds_once_and_keeps_existing_password(self):
        call_command("bootstrap")
        call_command("bootstrap")
        self.assertEqual(Governorate.objects.filter(name="محافظة تجريبية").count(), 1)
        self.assertTrue(
            Region.objects.filter(
                name="المنطقة الأولى", governorate__name="محافظة تجريبية"
            ).exists()
        )
        self.assertTrue(Region.objects.filter(name="المنطقة الثانية").exists())
        user = User.objects.get(username="inspector")
        user.set_password("changed-password-12")
        user.save()
        call_command("bootstrap")
        user.refresh_from_db()
        self.assertTrue(user.check_password("changed-password-12"))

    @patch.dict(os.environ, {**ENV, "ADMIN_PASSWORD": "short"}, clear=True)
    def test_short_password_stops_and_names_key(self):
        with self.assertRaisesMessage(CommandError, "ADMIN_PASSWORD"):
            call_command("bootstrap")

    @patch.dict(os.environ, ENV, clear=True)
    def test_missing_trial_governorate_for_inspector_names_it(self):
        Governorate.objects.create(name="محافظة أخرى")
        with self.assertRaisesMessage(CommandError, "محافظة تجريبية"):
            call_command("bootstrap")
