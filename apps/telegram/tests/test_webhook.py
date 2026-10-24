import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.complaints.models import Complaint
from apps.geography.models import Governorate, Region


class TelegramWebhookTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="الخليل")
        self.region = Region.objects.create(governorate=self.governorate, name="الحرم")
        self.inspector = User.objects.create_user(
            username="inspector", password="password-long-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="المفتش",
        )
        self.governor = User.objects.create_user(
            username="governor", password="password-long-12", role=User.Role.GOVERNOR,
            governorate=self.governorate, display_name="المدير",
        )
        self.secret = {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": "secret"}

    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret")
    def test_wrong_secret_is_forbidden(self):
        response = self.client.post("/api/telegram/webhook/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret")
    def test_duplicate_update_creates_one_complaint_and_one_pending_outbox(self):
        from apps.telegram.models import TelegramOutbox
        update = {
            "update_id": 7,
            "message": {"chat": {"id": 200}, "from": {"id": 200}, "text": "/complaint 1 1 عنوان النص"},
        }
        first = self.client.post("/api/telegram/webhook/", update, content_type="application/json", **self.secret)
        second = self.client.post("/api/telegram/webhook/", update, content_type="application/json", **self.secret)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 1)
        self.assertEqual(TelegramOutbox.objects.filter(status="pending").count(), 1)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret")
    def test_draft_is_not_complaint_until_complete(self):
        from apps.telegram.models import TelegramDraft

        update = {"update_id": 8, "message": {"chat": {"id": 201}, "from": {"id": 201}, "text": "/complaint"}}
        self.client.post("/api/telegram/webhook/", update, content_type="application/json", **self.secret)
        self.assertEqual(Complaint.objects.count(), 0)
        self.assertTrue(TelegramDraft.objects.filter(chat_id="201").exists())

    def test_link_token_is_single_use(self):
        from apps.telegram.links import create_staff_link, consume_staff_link

        with self.settings(TELEGRAM_BOT_TOKEN="token", TELEGRAM_BOT_USERNAME="ourbot"):
            link = create_staff_link(self.inspector)
        token = link.rsplit("=", 1)[1]
        self.assertTrue(consume_staff_link(token, "991"))
        self.assertFalse(consume_staff_link(token, "992"))

    def test_unlinked_staff_action_is_rejected(self):
        from apps.telegram.webhook import handle_update

        handle_update({
            "message": {"chat": {"id": 300}, "from": {"id": 300}, "text": "/accept 1"}
        })
        from apps.telegram.models import TelegramOutbox
        self.assertEqual(TelegramOutbox.objects.latest("pk").text, "هذا الحساب غير مربوط. اطلب رابط الربط من مدير النظام.")

    def test_citizen_message_only_for_telegram_complaints(self):
        from apps.telegram.models import TelegramOutbox
        from apps.telegram.webhook import _citizen_resolution

        telegram = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="عنوان المحل", body="النص",
            source=Complaint.Source.TELEGRAM, telegram_chat_id="400", telegram_user_id="400",
        )
        web = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="ويب", body="النص",
        )
        _citizen_resolution(telegram)
        _citizen_resolution(web)
        self.assertEqual(TelegramOutbox.objects.count(), 1)
        self.assertEqual(TelegramOutbox.objects.get().text, "تم التعامل مع الشكوى تبعك: عنوان المحل.")

    def test_empty_price_and_crossing_messages(self):
        from apps.telegram.models import TelegramOutbox
        from apps.telegram.webhook import handle_update

        handle_update({"message": {"chat": {"id": 501}, "from": {"id": 501}, "text": "/prices"}})
        handle_update({"message": {"chat": {"id": 502}, "from": {"id": 502}, "text": "/crossings"}})
        self.assertEqual(
            list(TelegramOutbox.objects.values_list("text", flat=True)),
            ["لا توجد قائمة أسعار منشورة.", "لا توجد حركة معابر منشورة."],
        )

    def test_legal_referral_does_not_notify_citizen_but_legal_close_does(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        legal = User.objects.create_user(
            username="legal", password="password-long-12", role=User.Role.LEGAL,
        )
        TelegramLink.objects.create(user=self.inspector, telegram_id="601")
        TelegramLink.objects.create(user=legal, telegram_id="602")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="عنوان المحل", body="النص",
            source=Complaint.Source.TELEGRAM, telegram_chat_id="600", telegram_user_id="600",
            inspector=self.inspector, status=Complaint.Status.FIELD,
        )
        handle_update({
            "message": {"chat": {"id": 601}, "from": {"id": 601}, "text": f"/field {complaint.pk} legal تفاصيل"}
        })
        self.assertFalse(TelegramOutbox.objects.filter(text__startswith="تم التعامل مع الشكوى تبعك").exists())
        handle_update({
            "message": {"chat": {"id": 602}, "from": {"id": 602}, "text": f"/close {complaint.pk}"}
        })
        self.assertTrue(TelegramOutbox.objects.filter(text="تم التعامل مع الشكوى تبعك: عنوان المحل.").exists())

    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret", TELEGRAM_BOT_TOKEN="token")
    def test_optional_photo_is_downloaded_into_the_created_complaint(self):
        get_file = Mock()
        get_file.raise_for_status.return_value = None
        get_file.json.return_value = {"result": {"file_path": "photos/complaint.jpg"}}
        download = Mock(content=b"fake-image")
        download.raise_for_status.return_value = None
        photo = {"update_id": 90, "message": {"chat": {"id": 700}, "from": {"id": 700}, "photo": [{"file_id": "file-1"}]}}
        with patch("apps.telegram.webhook.httpx.get", side_effect=[get_file, download]):
            self.client.post("/api/telegram/webhook/", photo, content_type="application/json", **self.secret)
        complete = {
            "update_id": 91,
            "message": {"chat": {"id": 700}, "from": {"id": 700}, "text": "/complaint 1 1 عنوان النص"},
        }
        self.client.post("/api/telegram/webhook/", complete, content_type="application/json", **self.secret)
        complaint = Complaint.objects.get()
        self.assertTrue(complaint.image)
        self.assertIn("complaint", complaint.image.name)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret")
    def test_incomplete_conversation_stays_a_draft(self):
        from apps.telegram.models import TelegramDraft

        def send(update_id, text):
            self.client.post(
                "/api/telegram/webhook/",
                {"update_id": update_id, "message": {"chat": {"id": 900}, "from": {"id": 900}, "text": text}},
                content_type="application/json",
                **self.secret,
            )

        send(900, "تقديم شكوى")
        send(901, "الخليل")

        self.assertEqual(Complaint.objects.count(), 0)
        draft = TelegramDraft.objects.get(chat_id="900")
        self.assertEqual(draft.step, "region")
        self.assertEqual(draft.payload["governorate"], self.governorate.pk)

    def test_web_complaint_notifies_linked_staff_only(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox

        TelegramLink.objects.create(user=self.inspector, telegram_id="801")
        TelegramLink.objects.create(user=self.governor, telegram_id="802")
        response = self.client.post("/api/complaints/public/", {
            "governorate": self.governorate.pk, "region": self.region.pk, "title": "محل", "body": "النص",
        })

        self.assertEqual(response.status_code, 201)
        texts = list(TelegramOutbox.objects.values_list("text", flat=True))
        self.assertEqual(texts, [
            f"وصلت شكوى في {self.region.name} بعنوان محل.",
            f"وصلت شكوى في {self.region.name} بعنوان محل.",
        ])

    def test_price_button_queues_the_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.publications.models import PriceReport
        from apps.telegram.models import TelegramOutbox
        from apps.telegram.webhook import handle_update

        PriceReport.objects.create(
            image=SimpleUploadedFile("price.png", b"img", content_type="image/png"),
            publisher_name="ناشر",
        )
        handle_update({"message": {"chat": {"id": 1}, "from": {"id": 1}, "text": "قائمة الأسعار"}})

        item = TelegramOutbox.objects.get()
        self.assertIn("price", item.photo)
        self.assertEqual(item.text, "")

    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret")
    def test_non_numeric_complaint_command_stays_a_single_update(self):
        from apps.telegram.models import TelegramUpdate

        update = {
            "update_id": 77,
            "message": {"chat": {"id": 770}, "from": {"id": 770}, "text": "/complaint الخليل الحرم عنوان نص"},
        }
        response = self.client.post("/api/telegram/webhook/", update, content_type="application/json", **self.secret)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)
        self.assertTrue(TelegramUpdate.objects.filter(update_id=77).exists())

    def test_web_close_tells_the_telegram_citizen_and_close_keeps_the_notes(self):
        from apps.complaints.models import FollowUp
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        legal = User.objects.create_user(
            username="legal-web", password="password-long-12", role=User.Role.LEGAL, display_name="قانوني",
        )
        TelegramLink.objects.create(user=legal, telegram_id="880")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="عنوان المحل", body="النص",
            source=Complaint.Source.TELEGRAM, telegram_chat_id="881", telegram_user_id="881",
            status=Complaint.Status.LEGAL, legal_referred_at=timezone.now(),
        )
        self.client.force_login(legal)
        closed = self.client.post(
            f"/api/complaints/{complaint.pk}/legal-close/",
            data=json.dumps({"notes": "تمت المعالجة بالكامل"}),
            content_type="application/json",
        )

        self.assertEqual(closed.status_code, 200)
        self.assertTrue(TelegramOutbox.objects.filter(text="تم التعامل مع الشكوى تبعك: عنوان المحل.").exists())

        complaint.status = Complaint.Status.LEGAL
        complaint.closed_at = None
        complaint.save()
        handle_update({
            "message": {"chat": {"id": 880}, "from": {"id": 880}, "text": f"/close {complaint.pk} تمت المعالجة بالكامل"},
        })
        self.assertEqual(FollowUp.objects.latest("pk").body, "تمت المعالجة بالكامل")

    def test_public_keyboard_has_the_three_buttons(self):
        from apps.telegram.outbox import keyboard_for

        labels = [button["text"] for row in keyboard_for("missing")["keyboard"] for button in row]
        self.assertEqual(labels, ["تقديم شكوى", "قائمة الأسعار", "حركة المعابر"])

    def test_register_webhook_failure_keeps_unregistered_status(self):
        from apps.telegram.models import TelegramWebhookStatus
        from apps.telegram.webhook import register_webhook

        with self.settings(TELEGRAM_BOT_TOKEN="token", TELEGRAM_WEBHOOK_SECRET="secret", PUBLIC_BASE_URL="https://test.example"):
            with patch("apps.telegram.webhook.httpx.post", side_effect=RuntimeError("offline")):
                register_webhook()
        status = TelegramWebhookStatus.objects.get()
        self.assertFalse(status.registered)
        self.assertIn("offline", status.last_error)
