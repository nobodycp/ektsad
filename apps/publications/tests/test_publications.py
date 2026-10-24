from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import User
from apps.publications.models import CrossingReport, PriceReport


class PublicationsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="password-12345", display_name="مدير النظام",
            role=User.Role.ADMIN,
        )
        self.publisher = User.objects.create_user(
            username="publisher", password="password-12345", display_name="ناشر الأسعار",
            role=User.Role.INSPECTOR, can_publish_prices=True, can_publish_crossings=True,
        )

    def test_public_latest_hides_older_rows_and_complaints(self):
        PriceReport.objects.create(
            image=SimpleUploadedFile("old.png", b"old", content_type="image/png"),
            publisher_name="ناشر قديم",
        )
        newest = PriceReport.objects.create(
            image=SimpleUploadedFile("new.png", b"new", content_type="image/png"),
            publisher_name="ناشر جديد",
        )

        older = self.client.get("/api/prices/")
        self.assertEqual(older.status_code, 403)
        latest = self.client.get("/api/prices/latest/")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["id"], newest.id)
        self.assertNotIn("complaints", latest.json())

    def test_crossing_without_text_and_image_is_rejected(self):
        self.client.force_login(self.publisher)

        response = self.client.post("/api/crossings/", {})

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())
        self.assertEqual(CrossingReport.objects.count(), 0)

    def test_system_admin_can_publish_and_read_rows(self):
        PriceReport.objects.create(
            image=SimpleUploadedFile("price.png", b"image", content_type="image/png"),
            publisher_name="ناشر",
        )
        self.client.force_login(self.admin)

        published = self.client.post(
            "/api/prices/",
            {"image": SimpleUploadedFile("new.png", b"image", content_type="image/png")},
        )
        listing = self.client.get("/api/prices/")

        self.assertEqual(published.status_code, 201)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 2)

    def test_user_with_publish_flag_can_publish_and_copies_display_name(self):
        self.client.force_login(self.publisher)

        response = self.client.post(
            "/api/prices/",
            {"image": SimpleUploadedFile("price.webp", b"image", content_type="image/webp")},
        )

        self.assertEqual(response.status_code, 201)
        report = PriceReport.objects.get()
        self.assertEqual(report.publisher, self.publisher)
        self.assertEqual(report.publisher_name, "ناشر الأسعار")

    def test_empty_latest_returns_exact_arabic_sentence(self):
        prices = self.client.get("/api/prices/latest/")
        crossings = self.client.get("/api/crossings/latest/")

        self.assertEqual(prices.status_code, 200)
        self.assertEqual(prices.json(), {"detail": "لا توجد قائمة أسعار منشورة."})
        self.assertEqual(crossings.status_code, 200)
        self.assertEqual(crossings.json(), {"detail": "لا توجد حركة معابر منشورة."})

    def test_anonymous_cannot_get_prices(self):
        response = self.client.get("/api/prices/")

        self.assertEqual(response.status_code, 403)
