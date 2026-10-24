import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.geography.models import Governorate


ENV = {
    "DJANGO_SECRET_KEY": "test-secret",
    "ALLOWED_HOSTS": "localhost",
    "BEHIND_PROXY": "0",
    "POSTGRES_DB": "test",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test-password",
}


class BootstrapTests(TestCase):
    @patch.dict(os.environ, ENV, clear=True)
    def test_bootstrap_creates_only_the_admin_and_keeps_the_password(self):
        call_command("bootstrap")
        call_command("bootstrap")
        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["admin"])
        self.assertEqual(Governorate.objects.count(), 0)
        user = User.objects.get(username="admin")
        user.set_password("changed-password-12")
        user.save()
        call_command("bootstrap")
        user.refresh_from_db()
        self.assertTrue(user.check_password("changed-password-12"))

    @patch.dict(os.environ, {k: v for k, v in ENV.items() if k != "POSTGRES_DB"}, clear=True)
    def test_missing_database_name_stops_and_names_key(self):
        with self.assertRaisesMessage(CommandError, "POSTGRES_DB"):
            call_command("bootstrap")

