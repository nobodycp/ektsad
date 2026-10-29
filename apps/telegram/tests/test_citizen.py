from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.complaints.models import Complaint
from apps.geography.models import Governorate, Region
from apps.telegram.models import TelegramDraft, TelegramLink, TelegramOutbox
from apps.telegram.webhook import handle_update


@override_settings(PUBLIC_BASE_URL="https://test.example")
class CitizenComplaintTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="الخليل")
        self.region = Region.objects.create(governorate=self.governorate, name="الحرم")
        self.inspector = User.objects.create_user(
            username="inspector", password="password-long-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="المفتش",
        )

    def say(self, text, chat=910, user=910):
        handle_update({"message": {"chat": {"id": chat}, "from": {"id": user}, "text": text}})

    def press(self, data, chat=910, user=910):
        handle_update({
            "callback_query": {
                "id": "cb", "from": {"id": user}, "data": data,
                "message": {"chat": {"id": chat}, "message_id": 1},
            }
        })

    def labels(self, markup):
        rows = markup.get("keyboard") or []
        return [button["text"] for row in rows for button in row]

    def latest(self, chat="910"):
        return TelegramOutbox.objects.filter(chat_id=chat).latest("pk")

    def test_citizen_start_welcomes_and_colors_each_public_button(self):
        self.say("/start", chat=50, user=50)
        item = self.latest("50")
        self.assertIn("أهلاً وسهلاً بك عزيز المواطن", item.text)
        rows = item.markup["keyboard"]
        self.assertEqual([row[0]["text"] for row in rows], ["تقديم شكوى", "القائمة الاسترشادية", "حركة المعابر"])
        self.assertEqual([row[0].get("style") for row in rows], ["danger", "primary", "success"])

    def test_linked_staff_start_has_no_welcome(self):
        TelegramLink.objects.create(user=self.inspector, telegram_id="51")
        self.say("/start", chat=51, user=51)
        item = self.latest("51")
        self.assertNotIn("عزيز المواطن", item.text)
        self.assertIn("الشكاوى", self.labels(item.markup))

    def test_fixed_kind_reaches_confirmation_then_stores_a_number(self):
        self.say("تقديم شكوى")
        self.assertIn("الخطوة 1 من 8", self.latest().text)
        self.assertIn("يرجى اختيار نوع الشكوى", self.latest().text)
        self.press("k:price")
        self.assertIn("الخطوة 2 من 8", self.latest().text)
        self.press(f"g:{self.governorate.pk}")
        self.press(f"n:{self.region.pk}")
        self.say("محل")
        self.say("النص")
        self.press("sk")
        self.assertIn("أخذ الموقع الآن", self.labels(self.latest().markup))
        self.assertIn("تحديد موقع على الخريطة", self.labels(self.latest().markup))
        map_button = next(
            button for row in self.latest().markup["keyboard"] for button in row
            if button["text"] == "تحديد موقع على الخريطة"
        )
        self.assertEqual(map_button["web_app"]["url"], "https://test.example/telegram/map/")
        self.press("locskip")
        text = self.latest().text
        self.assertIn("تأكيد الشكوى", text)
        self.assertIn("النوع: غلاء أسعار", text)
        self.assertIn("الموقع: بدون موقع", text)
        self.press("ok")
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.kind, "غلاء أسعار")
        self.assertIsNone(complaint.latitude)
        receipt = self.latest()
        self.assertIn(f"رقم الشكوى: {complaint.pk}", receipt.text)
        self.assertIn("تقديم شكوى", self.labels(receipt.markup))

    def test_other_kind_is_typed_and_location_is_kept(self):
        self.say("تقديم شكوى")
        self.press("k:other")
        self.assertIn("الخطوة 2 من 9", self.latest().text)
        self.say("سلعة تالفة")
        self.press(f"g:{self.governorate.pk}")
        self.press(f"n:{self.region.pk}")
        self.say("محل")
        self.say("النص")
        self.press("sk")
        handle_update({
            "message": {
                "chat": {"id": 910}, "from": {"id": 910},
                "location": {"latitude": 31.5, "longitude": 35.1},
            }
        })
        self.assertIn("الموقع: تم إرفاقه", self.latest().text)
        self.press("ok")
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.kind, "سلعة تالفة")
        self.assertEqual(float(complaint.latitude), 31.5)
        self.assertEqual(float(complaint.longitude), 35.1)
        self.client.force_login(self.inspector)
        detail = self.client.get(f"/api/complaints/{complaint.pk}/").json()
        self.assertEqual(detail["kind"], "سلعة تالفة")
        self.assertIn("31.5", detail["map_url"])

    def test_map_page_is_public(self):
        response = self.client.get("/telegram/map/")
        self.assertContains(response, "telegram-web-app.js")
        self.assertContains(response, "تأكيد")

    def test_pressing_submit_again_can_resume(self):
        self.say("تقديم شكوى")
        self.press("k:price")
        self.say("تقديم شكوى")
        self.assertIn("تكمل الشكوى الحالية", self.latest().text)
        self.press("resume")
        self.assertIn("الخطوة 2 من 8", self.latest().text)
        self.assertEqual(TelegramDraft.objects.get(chat_id="910").step, "governorate")

    def test_back_from_governorate_returns_to_the_kind(self):
        self.say("تقديم شكوى")
        self.press("k:price")
        self.say("رجوع")
        self.assertIn("يرجى اختيار نوع الشكوى", self.latest().text)
        self.assertEqual(TelegramDraft.objects.get(chat_id="910").step, "kind")
