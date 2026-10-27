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

    def test_linked_sender_keeps_the_messaging_username_and_presence(self):
        from apps.telegram.models import TelegramLink
        from apps.telegram.webhook import handle_update

        TelegramLink.objects.create(user=self.inspector, telegram_id="770")
        handle_update({
            "message": {"chat": {"id": 770}, "from": {"id": 770, "username": "Ahmad_1"}, "text": "/start"},
        })
        link = TelegramLink.objects.get(telegram_id="770")
        self.assertEqual(link.telegram_username, "Ahmad_1")
        self.assertIsNotNone(link.last_seen_at)
        from apps.telegram.presence import button_label
        label = button_label(User.objects.select_related("telegram_link").get(pk=self.inspector.pk))
        self.assertIn("✈ @Ahmad_1", label)
        self.assertIn("متصل", label)
        self.assertLessEqual(len(label), 64)

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
        self.assertTrue(TelegramOutbox.objects.filter(chat_id="602", text__startswith="لديك شكوى جديدة.").exists())
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
        details = (
            f"المحافظة: {self.governorate.name}\n"
            f"المنطقة: {self.region.name}\n"
            "العنوان: محل\n"
            "المحتوى: النص"
        )
        self.assertCountEqual(texts, [f"لديك شكوى جديدة.\n{details}", f"وصلت شكوى.\n{details}"])

    def test_inspector_arrival_message_has_accept_button(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        TelegramLink.objects.create(user=self.inspector, telegram_id="811")
        TelegramLink.objects.create(user=self.governor, telegram_id="812")
        self.client.post("/api/complaints/public/", {
            "governorate": self.governorate.pk, "region": self.region.pk, "title": "محل", "body": "النص",
        })
        complaint = Complaint.objects.get()
        inspector_message = TelegramOutbox.objects.get(chat_id="811")
        governor_message = TelegramOutbox.objects.get(chat_id="812")

        self.assertEqual(self.button_labels(inspector_message.markup)[0], "قبول")
        self.assertIn("رفض وإرجاع للمدير", self.button_labels(inspector_message.markup))
        self.assertIn("رجوع", self.button_labels(inspector_message.markup))
        self.assertEqual(self.button_labels(governor_message.markup)[0], "فتح")
        self.assertIn("رجوع", self.button_labels(governor_message.markup))

        handle_update({
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 811},
                "data": f"/accept {complaint.pk}",
                "message": {"chat": {"id": 811}, "message_id": 4},
            }
        })
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.FIELD)

    def test_return_to_the_governor_requires_a_reason_and_notifies_him(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        TelegramLink.objects.create(user=self.inspector, telegram_id="701")
        TelegramLink.objects.create(user=self.governor, telegram_id="702")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل السوق", body="النص",
        )
        handle_update({
            "callback_query": {
                "id": "rj-1", "from": {"id": 701}, "data": f"rj:{complaint.pk}",
                "message": {"chat": {"id": 701}, "message_id": 3},
            }
        })
        self.assertIn("اكتب سبب الرفض والإرجاع.", TelegramOutbox.objects.filter(chat_id="701").latest("pk").text)
        handle_update({"message": {"chat": {"id": 701}, "from": {"id": 701}, "text": "   "}})
        complaint.refresh_from_db()
        self.assertIsNone(complaint.returned_at)
        handle_update({"message": {"chat": {"id": 701}, "from": {"id": 701}, "text": "ليست من اختصاص المنطقة"}})
        complaint.refresh_from_db()
        self.assertEqual(complaint.return_reason, "ليست من اختصاص المنطقة")
        note = TelegramOutbox.objects.get(chat_id="702")
        self.assertIn("أُعيدت إليك شكوى لتوجيهها إلى مفتش آخر.", note.text)
        self.assertIn("ليست من اختصاص المنطقة", note.text)
        self.assertEqual(self.button_labels(note.markup)[0], "توجيه")
        self.assertIn("فتح", self.button_labels(note.markup))
        self.assertIsNone(complaint.inspector_id)

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

    def test_public_menu_is_inline_and_staff_get_complaints(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        handle_update({"message": {"chat": {"id": 50}, "from": {"id": 50}, "text": "/start"}})
        labels = self.button_labels(TelegramOutbox.objects.get(chat_id="50").markup)
        self.assertEqual(labels, ["تقديم شكوى", "حركة المعابر", "القائمة الاسترشادية"])
        self.assertIn("keyboard", TelegramOutbox.objects.get(chat_id="50").markup)
        self.assertNotIn("رجوع", labels)

        TelegramLink.objects.create(user=self.inspector, telegram_id="51")
        handle_update({"message": {"chat": {"id": 51}, "from": {"id": 51}, "text": "/start"}})
        self.assertIn("الشكاوى", self.button_labels(TelegramOutbox.objects.get(chat_id="51").markup))

    def test_complaint_choices_are_buttons_and_text_is_only_title_and_body(self):
        from apps.telegram.models import TelegramDraft, TelegramOutbox

        self.say("تقديم شكوى", chat=910, user=910)
        self.assertIn("الخليل", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press(f"g:{self.governorate.pk}", chat=910, user=910)
        self.assertEqual(TelegramDraft.objects.get(chat_id="910").step, "region")
        self.assertIn("الحرم", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press(f"n:{self.region.pk}", chat=910, user=910)
        self.assertIn("أرسل عنوان الشكوى.", TelegramOutbox.objects.latest("pk").text)
        self.say("محل", chat=910, user=910)
        self.assertIn("أرسل نص الشكوى.", TelegramOutbox.objects.latest("pk").text)
        self.say("النص", chat=910, user=910)
        self.assertIn("تخطي", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press("sk", chat=910, user=910)
        self.assertIn("تقديم", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press("ok", chat=910, user=910)

        complaint = Complaint.objects.get()
        self.assertEqual(complaint.title, "محل")
        self.assertEqual(complaint.body, "النص")
        self.assertEqual(complaint.region, self.region)
        self.assertEqual(TelegramOutbox.objects.filter(chat_id="910", text="تم استلام الشكوى.").count(), 1)

    def test_complaints_button_opens_the_complaint(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox

        TelegramLink.objects.create(user=self.inspector, telegram_id="920")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل السوق", body="النص الكامل",
        )
        self.press("ls:r:0", chat=920, user=920)
        self.assertTrue(any("محل السوق" in label for label in self.button_labels(TelegramOutbox.objects.latest("pk").markup)))
        self.press(f"op:{complaint.pk}", chat=920, user=920)
        detail = TelegramOutbox.objects.latest("pk")
        self.assertIn("المحافظة: الخليل", detail.text)
        self.assertIn("المنطقة: الحرم", detail.text)
        self.assertIn("العنوان: محل السوق", detail.text)
        self.assertIn("المحتوى: النص الكامل", detail.text)
        self.assertIn("قبول", self.button_labels(detail.markup))

    def test_reply_button_then_destination_buttons(self):
        from apps.complaints.models import FollowUp
        from apps.telegram.models import TelegramLink, TelegramOutbox

        TelegramLink.objects.create(user=self.inspector, telegram_id="930")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل", body="النص",
            source=Complaint.Source.TELEGRAM, telegram_chat_id="931", telegram_user_id="931",
            inspector=self.inspector, status=Complaint.Status.FIELD,
        )
        self.press(f"ry:{complaint.pk}", chat=930, user=930)
        self.assertIn("اكتب نتيجة الكشف.", TelegramOutbox.objects.latest("pk").text)
        self.say("الكشف سليم", chat=930, user=930)
        labels = self.button_labels(TelegramOutbox.objects.latest("pk").markup)
        self.assertIn("مدير المحافظة وحدها", labels)
        self.assertIn("مدير المحافظة والشؤون القانونية", labels)
        self.press(f"dl:{complaint.pk}", chat=930, user=930)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.LEGAL)
        self.assertEqual(FollowUp.objects.get().body, "الكشف سليم")
        self.assertFalse(TelegramOutbox.objects.filter(chat_id="931").exists())

        complaint.status = Complaint.Status.FIELD
        complaint.legal_referred_at = None
        complaint.save()
        self.press(f"ry:{complaint.pk}", chat=930, user=930)
        self.say("أُغلق ميدانياً", chat=930, user=930)
        self.press(f"dg:{complaint.pk}", chat=930, user=930)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.FINISHED)
        self.assertTrue(TelegramOutbox.objects.filter(chat_id="931", text="تم التعامل مع الشكوى تبعك: محل.").exists())

    def test_governor_assigns_from_inspector_buttons(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox

        TelegramLink.objects.create(user=self.governor, telegram_id="940")
        TelegramLink.objects.create(user=self.inspector, telegram_id="941")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل", body="النص",
        )
        self.press(f"op:{complaint.pk}", chat=940, user=940)
        self.assertIn("توجيه", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press(f"as:{complaint.pk}", chat=940, user=940)
        self.assertIn("المفتش", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press(f"in:{complaint.pk}:{self.inspector.pk}", chat=940, user=940)
        complaint.refresh_from_db()
        self.assertEqual(complaint.inspector, self.inspector)
        self.assertEqual(complaint.status, Complaint.Status.FIELD)
        inspector_card = TelegramOutbox.objects.filter(chat_id="941").latest("pk")
        self.assertIn("رد", self.button_labels(inspector_card.markup))

    def test_legal_close_button_finishes_without_typing(self):
        from apps.complaints.models import FollowUp
        from apps.telegram.models import TelegramLink, TelegramOutbox

        legal = User.objects.create_user(
            username="legal-btn", password="password-long-12", role=User.Role.LEGAL, display_name="قانوني",
        )
        TelegramLink.objects.create(user=legal, telegram_id="950")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل", body="النص",
            source=Complaint.Source.TELEGRAM, telegram_chat_id="951", telegram_user_id="951",
            status=Complaint.Status.LEGAL, legal_referred_at=timezone.now(),
        )
        self.press(f"op:{complaint.pk}", chat=950, user=950)
        self.assertIn("تم الانجاز", self.button_labels(TelegramOutbox.objects.latest("pk").markup))
        self.press(f"dn:{complaint.pk}", chat=950, user=950)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.RESOLVED)
        self.assertEqual(FollowUp.objects.get().body, "تم الانجاز")
        self.assertTrue(TelegramOutbox.objects.filter(text="تم التعامل مع الشكوى تبعك: محل.").exists())

    def test_screens_use_the_reply_keyboard(self):
        import os
        from apps.telegram.models import TelegramOutbox
        from apps.telegram.outbox import send_telegram_outbox

        TelegramOutbox.objects.create(
            chat_id="1", text="اختر المحافظة.",
            markup={"inline_keyboard": [[{"text": "الخليل", "callback_data": "g:1"}]]},
        )
        sent = Mock()
        sent.raise_for_status.return_value = None
        sent.json.return_value = {"result": {"message_id": 9}}
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}):
            with patch("apps.telegram.outbox.httpx.post", return_value=sent) as post:
                self.assertEqual(send_telegram_outbox(), 1)
        self.assertEqual(post.call_count, 1)
        menu = post.call_args.kwargs["json"]
        self.assertEqual(menu["text"], "اختر المحافظة.")
        self.assertEqual(menu["reply_markup"]["keyboard"][0][0]["text"], "الخليل")
        self.assertNotIn("inline_keyboard", menu["reply_markup"])

    def say(self, text, chat, user):
        from apps.telegram.webhook import handle_update

        handle_update({"message": {"chat": {"id": chat}, "from": {"id": user}, "text": text}})

    def press(self, data, chat, user):
        from apps.telegram.webhook import handle_update

        handle_update({
            "callback_query": {
                "id": "cb",
                "from": {"id": user},
                "data": data,
                "message": {"chat": {"id": chat}, "message_id": 1},
            }
        })

    def button_labels(self, markup):
        rows = markup.get("keyboard") or markup.get("inline_keyboard") or []
        return [button["text"] for row in rows for button in row]

    def test_button_press_sends_the_next_screen_on_the_keyboard(self):
        from apps.telegram.models import TelegramOutbox

        self.press("nw", chat=960, user=960)
        item = TelegramOutbox.objects.get(chat_id="960")
        self.assertIn("اختر المحافظة.", item.text)
        self.assertIn("keyboard", item.markup)
        self.assertIn("رجوع", self.button_labels(item.markup))

    def test_complaints_button_opens_pending_work_when_nothing_is_incoming(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox

        TelegramLink.objects.create(user=self.inspector, telegram_id="970")
        Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="كشف مفتوح", body="النص",
            inspector=self.inspector, status=Complaint.Status.FIELD,
        )
        self.press("ls:a:0", chat=970, user=970)
        labels = self.button_labels(TelegramOutbox.objects.latest("pk").markup)
        self.assertTrue(any("كشف مفتوح" in label for label in labels))

    def test_photo_during_the_reply_keeps_the_reply(self):
        from apps.telegram.models import TelegramDraft, TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        TelegramLink.objects.create(user=self.inspector, telegram_id="980")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل", body="النص",
            inspector=self.inspector, status=Complaint.Status.FIELD,
        )
        TelegramDraft.objects.create(chat_id="980", step="field_text", payload={"field_complaint": complaint.pk})
        handle_update({"message": {"chat": {"id": 980}, "from": {"id": 980}, "photo": [{"file_id": "file-1"}]}})
        self.assertEqual(TelegramDraft.objects.get(chat_id="980").step, "field_text")
        self.assertIn("اكتب نتيجة الكشف.", TelegramOutbox.objects.latest("pk").text)
        self.assertNotIn("الصورة تُرفق بعد نص الشكوى.", TelegramOutbox.objects.latest("pk").text)

    def test_staff_menu_follows_role_permissions_and_missions_are_notified(self):
        from apps.accounts.models import StaffRole
        from apps.field_missions.services import open_mission
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        role = StaffRole.objects.create(
            name="مفتش التجربة", kind=StaffRole.Kind.INSPECTOR, can_view_field_missions=True,
        )
        self.inspector.staff_role = role
        self.inspector.save(update_fields=["staff_role"])
        TelegramLink.objects.create(user=self.inspector, telegram_id="990")
        handle_update({"message": {"chat": {"id": 990}, "from": {"id": 990}, "text": "/start"}})
        labels = self.button_labels(TelegramOutbox.objects.get(chat_id="990").markup)
        self.assertIn("المهمات", labels)
        self.assertNotIn("إنشاء مهمة", labels)
        self.assertNotIn("التقارير", labels)

        role.can_open_field_missions = True
        role.can_view_reports = True
        role.save(update_fields=["can_open_field_missions", "can_view_reports"])
        TelegramOutbox.objects.all().delete()
        handle_update({"message": {"chat": {"id": 990}, "from": {"id": 990}, "text": "/start"}})
        labels = self.button_labels(TelegramOutbox.objects.get(chat_id="990").markup)
        self.assertIn("إنشاء مهمة", labels)
        self.assertIn("التقارير", labels)

        TelegramOutbox.objects.all().delete()
        open_mission(self.inspector, {
            "kind": "ضبط", "priority": "عادي", "details": "بضاعة", "place_name": "محل", "phone": "0599000000",
        })
        note = TelegramOutbox.objects.get(chat_id="990")
        self.assertIn("لديك مهمة جديدة.", note.text)
        self.assertIn("محل", note.text)
        self.assertEqual(self.button_labels(note.markup)[0], "فتح")
        self.assertIn("رجوع", self.button_labels(note.markup))

    def test_system_owner_has_no_reports_button_on_the_bot(self):
        from apps.telegram.models import TelegramLink, TelegramOutbox
        from apps.telegram.webhook import handle_update

        admin = User.objects.create_user(
            username="owner", password="password-long-12", role=User.Role.ADMIN, display_name="مالك النظام",
        )
        TelegramLink.objects.create(user=admin, telegram_id="991")
        handle_update({"message": {"chat": {"id": 991}, "from": {"id": 991}, "text": "/start"}})
        labels = self.button_labels(TelegramOutbox.objects.get(chat_id="991").markup)
        self.assertNotIn("التقارير", labels)

        TelegramLink.objects.create(user=self.governor, telegram_id="992")
        TelegramOutbox.objects.all().delete()
        handle_update({"message": {"chat": {"id": 992}, "from": {"id": 992}, "text": "/start"}})
        self.assertIn("التقارير", self.button_labels(TelegramOutbox.objects.get(chat_id="992").markup))

        TelegramOutbox.objects.all().delete()
        self.press("rp", chat=991, user=991)
        self.assertEqual(TelegramOutbox.objects.get(chat_id="991").text, "غير مسموح.")

    def test_legal_and_redirected_inspector_get_arrival_notices(self):
        from apps.accounts.models import StaffRole
        from apps.complaints.services import accept_complaint, submit_field_report
        from apps.field_missions.services import open_mission, redirect_mission, reply_mission
        from apps.telegram.models import TelegramLink, TelegramOutbox

        legal = User.objects.create_user(
            username="legal-note", password="password-long-12", role=User.Role.LEGAL,
        )
        admin = User.objects.create_user(
            username="admin-note", password="password-long-12", role=User.Role.ADMIN,
        )
        role = StaffRole.objects.create(
            name="مفتش الإشعار", kind=StaffRole.Kind.INSPECTOR,
            can_view_field_missions=True, can_open_field_missions=True,
        )
        self.inspector.staff_role = role
        self.inspector.save(update_fields=["staff_role"])
        TelegramLink.objects.create(user=legal, telegram_id="660")
        TelegramLink.objects.create(user=self.inspector, telegram_id="661")
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="محل محوّل", body="النص",
            status=Complaint.Status.RECEIVED,
        )
        accept_complaint(complaint, self.inspector, channel="web", ip="1", telegram_id=None)
        submit_field_report(complaint, self.inspector, "للقانوني", [], "legal")
        legal_complaint = TelegramOutbox.objects.get(chat_id="660")
        self.assertTrue(legal_complaint.text.startswith("لديك شكوى جديدة."))
        self.assertIn("محل محوّل", legal_complaint.text)
        self.assertEqual(self.button_labels(legal_complaint.markup)[0], "فتح")

        TelegramOutbox.objects.all().delete()
        waiting = open_mission(admin, {
            "scope": "office", "governorate": self.governorate.pk,
            "kind": "ضبط", "priority": "عادي", "details": "بضاعة", "place_name": "المحل", "phone": "0599000000",
        })
        self.assertFalse(TelegramOutbox.objects.filter(chat_id="661").exists())
        redirect_mission(self.governor, waiting, self.inspector.pk)
        self.assertTrue(TelegramOutbox.objects.filter(chat_id="661", text__startswith="لديك مهمة جديدة.").exists())

        TelegramOutbox.objects.all().delete()
        mission = open_mission(self.inspector, {
            "kind": "ضبط", "priority": "عادي", "details": "بضاعة", "place_name": "محل المهمة", "phone": "0599000000",
        })
        reply_mission(self.inspector, mission, "أُحيلت", [], "legal")
        legal_mission = TelegramOutbox.objects.get(chat_id="660")
        self.assertTrue(legal_mission.text.startswith("لديك مهمة جديدة."))
        self.assertIn("محل المهمة", legal_mission.text)

    def test_register_webhook_failure_keeps_unregistered_status(self):
        from apps.telegram.models import TelegramWebhookStatus
        from apps.telegram.webhook import register_webhook

        with self.settings(TELEGRAM_BOT_TOKEN="token", TELEGRAM_WEBHOOK_SECRET="secret", PUBLIC_BASE_URL="https://test.example"):
            with patch("apps.telegram.webhook.httpx.post", side_effect=RuntimeError("offline")):
                register_webhook()
        status = TelegramWebhookStatus.objects.get()
        self.assertFalse(status.registered)
        self.assertIn("offline", status.last_error)
