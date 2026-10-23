from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.services import set_user_password
from apps.geography.models import Governorate, Region


class AuthenticationTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="محافظة تجريبية")
        self.region = Region.objects.create(
            governorate=self.governorate, name="المنطقة الأولى"
        )

    def test_login_failure_is_generic_and_short_password_rejected(self):
        user = User(username="inspector", role=User.Role.INSPECTOR,
                    governorate=self.governorate, region=self.region)
        with self.assertRaises(ValidationError):
            set_user_password(user, "short-pass")
        response = self.client.post(
            "/api/auth/login/",
            {"username": "missing", "password": "wrong-password-1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "بيانات الدخول غير صحيحة.")

    def test_inactive_user_cannot_log_in(self):
        user = User.objects.create_user(
            username="inactive",
            password="valid-password-12",
            role=User.Role.LEGAL,
            is_active=False,
        )
        response = self.client.post(
            "/api/auth/login/",
            {"username": user.username, "password": "valid-password-12"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "بيانات الدخول غير صحيحة.")

    def test_patch_does_not_change_username(self):
        user = User.objects.create_user(
            username="legal",
            password="valid-password-12",
            role=User.Role.LEGAL,
        )
        self.client.force_login(user)
        response = self.client.patch(
            f"/api/users/{user.pk}/",
            data='{"username": "changed", "display_name": "محدّث"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "legal")
        self.assertEqual(user.display_name, "محدّث")

    def test_geography_api_rejects_non_admin(self):
        user = User.objects.create_user(
            username="legal",
            password="valid-password-12",
            role=User.Role.LEGAL,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/governorates/").status_code, 403)
