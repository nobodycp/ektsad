from django.test import TestCase, override_settings


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
