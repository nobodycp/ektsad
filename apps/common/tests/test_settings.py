from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.common.models import SystemSettings


class SystemSettingsTests(TestCase):
    def test_public_flag_and_admin_telegram_fields(self):
        User = get_user_model()
        admin = User.objects.create_user(username="admin", password="admin-password-12", role="admin", display_name="مدير")
        self.client.force_login(admin)

        public = self.client.get("/api/settings/public/")
        self.assertEqual(public.json()["web_complaints_enabled"], True)

        saved = self.client.patch(
            "/api/system-settings/",
            data={"web_complaints_enabled": False, "telegram_bot_username": "@deskbot", "telegram_bot_token": "123:abc"},
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200)
        body = saved.json()
        self.assertFalse(body["web_complaints_enabled"])
        self.assertEqual(body["telegram_bot_username"], "deskbot")
        self.assertTrue(body["telegram_bot_configured"])
        self.assertNotIn("telegram_bot_token", body)
        self.assertEqual(SystemSettings.current().telegram_bot_token, "123:abc")
        self.assertFalse(self.client.get("/api/settings/public/").json()["web_complaints_enabled"])
