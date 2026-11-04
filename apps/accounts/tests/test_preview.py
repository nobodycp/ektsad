import json

from django.test import TestCase

from apps.accounts.models import StaffRole, User
from apps.geography.models import Governorate, Region


class PreviewRoleTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="غزة")
        self.region = Region.objects.create(governorate=self.governorate, name="الزيتون")
        self.preview = User.objects.create_user(
            username="preview",
            password="preview-password-12",
            role=User.Role.CUSTOM,
            display_name="يوزر استعراضي",
            is_preview=True,
            staff_role=StaffRole.objects.get(name="مدير المحافظات"),
        )
        self.inspector = User.objects.create_user(
            username="inspector",
            password="preview-password-12",
            role=User.Role.INSPECTOR,
            display_name="مفتش",
            governorate=self.governorate,
            region=self.region,
        )

    def post(self, payload):
        return self.client.post(
            "/api/auth/preview-role/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_only_the_preview_account_can_wear_each_role(self):
        self.client.force_login(self.inspector)
        self.assertEqual(self.post({"role": "legal"}).status_code, 403)

        self.client.force_login(self.preview)
        self.assertEqual(self.post({"role": "inspector"}).status_code, 400)
        switched = self.post({
            "role": "inspector",
            "governorate": self.governorate.pk,
            "region": self.region.pk,
        })
        self.assertEqual(switched.status_code, 200)
        self.assertEqual(switched.json()["role"], "inspector")
        self.assertEqual(switched.json()["role_name"], "مفتش")
        self.assertTrue(switched.json()["is_preview"])
        self.preview.refresh_from_db()
        self.assertEqual(self.preview.region, self.region)

        legal = self.post({"role": "legal"})
        self.assertEqual(legal.json()["role"], "legal")
        self.assertEqual(legal.json()["role_name"], "الشؤون القانونية")
        self.preview.refresh_from_db()
        self.assertIsNone(self.preview.governorate_id)
        self.assertIsNone(self.preview.region_id)

    def test_telegram_switches_the_preview_account_without_touching_another_user(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        TelegramLink.objects.create(user=self.preview, telegram_id="880")
        TelegramLink.objects.create(user=self.inspector, telegram_id="881")
        handle_update({"message": {"chat": {"id": 880}, "from": {"id": 880}, "text": "/start"}})
        labels = [
            button["text"]
            for row in TelegramOutbox.objects.get(chat_id="880").markup["keyboard"]
            for button in row
        ]
        self.assertIn("تغيير الصلاحية", labels)
        self.assertIn("يوزر استعراضي — مدير المحافظات", TelegramOutbox.objects.get(chat_id="880").text)

        handle_update({
            "callback_query": {
                "id": "cb",
                "from": {"id": 880},
                "data": "pv",
                "message": {"chat": {"id": 880}, "message_id": 1},
            }
        })
        choices = [
            button["text"]
            for row in TelegramOutbox.objects.filter(chat_id="880").latest("pk").markup["keyboard"]
            for button in row
        ]
        self.assertIn("مدير المحافظة", choices)
        self.assertIn("المفتش", choices)
        self.assertIn("إداري المحافظة", choices)
        self.assertIn("الدخول كمواطن", choices)

        handle_update({
            "callback_query": {
                "id": "cb2",
                "from": {"id": 880},
                "data": f"pv:g:inspector:{self.governorate.pk}",
                "message": {"chat": {"id": 880}, "message_id": 1},
            }
        })
        self.assertIn("الزيتون", [
            button["text"]
            for row in TelegramOutbox.objects.filter(chat_id="880").latest("pk").markup["keyboard"]
            for button in row
        ])
        handle_update({
            "callback_query": {
                "id": "cb3",
                "from": {"id": 880},
                "data": f"pv:n:{self.governorate.pk}:{self.region.pk}",
                "message": {"chat": {"id": 880}, "message_id": 1},
            }
        })
        self.preview.refresh_from_db()
        self.inspector.refresh_from_db()
        self.assertEqual(self.preview.role, User.Role.INSPECTOR)
        self.assertEqual(self.preview.region, self.region)
        self.assertEqual(self.inspector.role, User.Role.INSPECTOR)
        self.assertEqual(TelegramLink.objects.get(telegram_id="881").user, self.inspector)
        self.assertIn("يوزر استعراضي — مفتش", TelegramOutbox.objects.filter(chat_id="880").latest("pk").text)

        handle_update({
            "callback_query": {
                "id": "cb4",
                "from": {"id": 880},
                "data": "pv:r:citizen",
                "message": {"chat": {"id": 880}, "message_id": 1},
            }
        })
        self.preview.refresh_from_db()
        self.assertTrue(self.preview.preview_as_citizen)
        self.assertIsNone(self.preview.staff_role_id)
        citizen = TelegramOutbox.objects.filter(chat_id="880").latest("pk")
        citizen_labels = [button["text"] for row in citizen.markup["keyboard"] for button in row]
        self.assertIn("أهلاً وسهلاً بك عزيز المواطن", citizen.text)
        self.assertIn("تقديم شكوى", citizen_labels)
        self.assertIn("القائمة الاسترشادية", citizen_labels)
        self.assertIn("حركة المعابر", citizen_labels)
        self.assertIn("تغيير الصلاحية", citizen_labels)
        self.assertNotIn("الشكاوى", citizen_labels)
