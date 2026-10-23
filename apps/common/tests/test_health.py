from django.conf import settings
from django.test import TestCase


class HealthTests(TestCase):
    def test_health_ok_and_debug_defaults_off(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertFalse(settings.DEBUG)
        self.assertEqual(settings.TIME_ZONE, "Asia/Hebron")
