import json

from django.test import TestCase

from apps.accounts.models import User
from apps.geography.models import Governorate, Region


class BotButtonTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="غزة")
        self.region = Region.objects.create(governorate=self.governorate, name="الرمال")
        self.admin = User.objects.create_user(
            username="admin", password="admin-password-12", role=User.Role.ADMIN,
        )
        self.inspector = User.objects.create_user(
            username="inspector", password="password-long-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="المفتش",
        )
        self.client.force_login(self.admin)

    def test_new_button_opens_the_button_it_points_at(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        created = self.client.post(
            "/api/telegram/buttons/",
            data=json.dumps({
                "label": "المتابعة", "target": "ls:a:0", "audience": "linked",
                "row": 3, "position": 2, "enabled": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["target_label"], "الشكاوى")

        denied = self.client.post(
            "/api/telegram/buttons/",
            data=json.dumps({
                "label": "المتابعة", "target": "ls:a:0", "audience": "linked",
                "row": 3, "position": 3, "enabled": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 400)

        TelegramLink.objects.create(user=self.inspector, telegram_id="440")
        handle_update({"message": {"chat": {"id": 440}, "from": {"id": 440}, "text": "/start"}})
        labels = [
            button["text"]
            for row in TelegramOutbox.objects.get(chat_id="440").markup["keyboard"]
            for button in row
        ]
        self.assertIn("المتابعة", labels)

        TelegramOutbox.objects.all().delete()
        handle_update({"message": {"chat": {"id": 440}, "from": {"id": 440}, "text": "المتابعة"}})
        self.assertIn("شكاوى", TelegramOutbox.objects.latest("pk").text)

    def test_inspector_cannot_edit_the_panel(self):
        self.client.force_login(self.inspector)
        self.assertEqual(self.client.get("/api/telegram/buttons/").status_code, 403)
