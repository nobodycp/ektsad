import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.complaints.models import Complaint
from apps.geography.models import Governorate, Region


class WhatsAppWebhookTests(TestCase):
    def test_meta_challenge_is_returned_only_for_the_agreed_token(self):
        url = "/api/whatsapp/webhook/"
        denied = self.client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "123"})
        self.assertEqual(denied.status_code, 403)

        with self.settings(WHATSAPP_VERIFY_TOKEN="agreed-token"):
            ok = self.client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "agreed-token", "hub.challenge": "987654"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content, b"987654")
        self.assertEqual(ok["Content-Type"], "text/plain")

    @override_settings(WHATSAPP_VERIFY_TOKEN="")
    def test_missing_token_rejects_the_challenge(self):
        response = self.client.get(
            "/api/whatsapp/webhook/",
            {"hub.mode": "subscribe", "hub.verify_token": "agreed-token", "hub.challenge": "1"},
        )
        self.assertEqual(response.status_code, 403)

    def test_incoming_messages_are_accepted(self):
        response = self.client.post("/api/whatsapp/webhook/", data=b"{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)


def _envelope(mid, phone, message):
    message = {"from": phone, "id": mid, **message}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {"messages": [message]}}]}],
    }


class WhatsAppComplaintFlowTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="الخليل")
        self.region = Region.objects.create(governorate=self.governorate, name="الحرم")
        self.sent = []
        self.patches = [
            patch("apps.whatsapp.flow.send_buttons", side_effect=self._buttons),
            patch("apps.whatsapp.flow.send_list", side_effect=self._list),
            patch("apps.whatsapp.flow.send_text", side_effect=self._text),
            patch("apps.whatsapp.flow.send_location_request", side_effect=self._location),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in self.patches])

    def _buttons(self, phone, body, buttons):
        self.sent.append(("buttons", body, [item["id"] for item in buttons]))

    def _list(self, phone, body, rows, button="اختر"):
        self.sent.append(("list", body, [item["id"] for item in rows]))

    def _text(self, phone, body):
        self.sent.append(("text", body))

    def _location(self, phone, body):
        self.sent.append(("location", body))

    def post(self, mid, message):
        response = self.client.post(
            "/api/whatsapp/webhook/",
            data=json.dumps(_envelope(mid, "15550363496", message)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_welcome_offers_the_three_public_actions(self):
        self.post("m1", {"type": "text", "text": {"body": "مرحبا"}})
        self.assertEqual(self.sent[-1][0], "buttons")
        self.assertIn("عزيز المواطن", self.sent[-1][1])
        self.assertEqual(self.sent[-1][2], ["nw", "pr", "cr"])

    def test_complaint_path_stores_kind_and_returns_a_number(self):
        self.post("a1", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "nw"}}})
        self.assertIn("الخطوة 1 من 8", self.sent[-1][1])
        self.assertIn("k:price", self.sent[-1][2])
        self.post("a2", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": "k:price"}}})
        self.assertIn("الخطوة 2 من 8", self.sent[-1][1])
        self.assertIn(f"g:{self.governorate.pk}", self.sent[-1][2])
        self.post("a3", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": f"g:{self.governorate.pk}"}}})
        self.post("a4", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": f"n:{self.region.pk}"}}})
        self.post("a5", {"type": "text", "text": {"body": "محل يغلي السكر"}})
        self.post("a6", {"type": "text", "text": {"body": "السعر ضعف الأسبوع الماضي"}})
        self.post("a7", {"type": "text", "text": {"body": "تخطي"}})
        self.assertEqual(self.sent[-1][0], "location")
        self.assertIn("الخطوة 7 من 8", self.sent[-1][1])
        self.post("a8", {"type": "text", "text": {"body": "تخطي"}})
        self.assertIn("بدون موقع", self.sent[-1][1])
        self.assertEqual(self.sent[-1][2], ["ok", "back"])
        self.post("a9", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "ok"}}})
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.source, "whatsapp")
        self.assertEqual(complaint.kind, "غلاء أسعار")
        self.assertIsNone(complaint.latitude)
        self.assertEqual(complaint.telegram_user_id, "15550363496")
        self.assertIn(f"رقم الشكوى: {complaint.pk}", self.sent[-1][1])
        self.assertEqual(self.sent[-1][2], ["nw", "pr", "cr"])

    def test_other_kind_and_a_location_message_are_stored(self):
        self.post("b1", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "nw"}}})
        self.post("b2", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": "k:other"}}})
        self.assertIn("الخطوة 2 من 9", self.sent[-1][1])
        self.post("b3", {"type": "text", "text": {"body": "سلعة تالفة"}})
        self.post("b4", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": f"g:{self.governorate.pk}"}}})
        self.post("b5", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": f"n:{self.region.pk}"}}})
        self.post("b6", {"type": "text", "text": {"body": "بضاعة"}})
        self.post("b7", {"type": "text", "text": {"body": "منتهية"}})
        self.post("b8", {"type": "text", "text": {"body": "تخطي"}})
        self.post("b9", {"type": "location", "location": {"latitude": 31.5, "longitude": 35.1}})
        self.assertIn("تم إرفاقه", self.sent[-1][1])
        self.post("b10", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "ok"}}})
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.kind, "سلعة تالفة")
        self.assertEqual(float(complaint.latitude), 31.5)

    def test_a_repeated_message_is_ignored(self):
        body = _envelope("same", "15550363496", {"type": "text", "text": {"body": "مرحبا"}})
        raw = json.dumps(body)
        self.client.post("/api/whatsapp/webhook/", data=raw, content_type="application/json")
        self.client.post("/api/whatsapp/webhook/", data=raw, content_type="application/json")
        self.assertEqual(len(self.sent), 1)

    def test_starting_again_offers_to_resume(self):
        self.post("c1", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "nw"}}})
        self.post("c2", {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": "k:price"}}})
        self.post("c3", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "nw"}}})
        self.assertIn("تكمل الشكوى", self.sent[-1][1])
        self.assertEqual(self.sent[-1][2], ["resume", "restart"])

    def test_a_real_whatsapp_message_id_is_stored(self):
        long_id = "wamid." + ("A" * 180)
        self.post(long_id, {"type": "text", "text": {"body": "مرحبا"}})
        self.assertIn("عزيز المواطن", self.sent[-1][1])

    def test_price_list_without_a_report_says_so(self):
        self.post("d1", {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "pr"}}})
        self.assertEqual(self.sent[-1], ("text", "لا توجد قائمة أسعار منشورة."))
