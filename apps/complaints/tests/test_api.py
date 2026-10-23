import json

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.models import User
from apps.complaints.models import Complaint
from apps.geography.models import Governorate, Region


class ComplaintApiTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="الخليل")
        self.region = Region.objects.create(governorate=self.governorate, name="الحرم")
        self.complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="عنوان", body="تفاصيل"
        )
        self.admin = User.objects.create_user(
            username="admin", password="password-123", role=User.Role.ADMIN,
        )
        self.inspector = User.objects.create_user(
            username="inspector", password="password-123", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region,
        )
        self.viewer = User.objects.create_user(
            username="viewer", password="password-123", role=User.Role.LEGAL,
            can_view_all_complaints=True,
        )

    def test_accept_many_ids_is_bad_request(self):
        self.client.force_login(self.inspector)
        response = self.client.post(
            "/api/complaints/actions/",
            data=json.dumps({"action": "accept", "ids": [self.complaint.pk, 99]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_view_all_user_is_read_only(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/api/complaints/").status_code, 200)
        response = self.client.post(
            "/api/complaints/actions/",
            data=json.dumps({"action": "flag", "ids": [self.complaint.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_media_is_denied(self):
        response = self.client.get(f"/api/media/complaints/{self.complaint.pk}/")
        self.assertIn(response.status_code, {403, 404})

    def test_public_success_has_no_id_and_eleventh_is_rate_limited(self):
        cache.clear()
        payload = {
            "governorate": self.governorate.pk, "region": self.region.pk,
            "title": "شكوى", "body": "تفاصيل",
        }
        response = self.client.post("/api/complaints/public/", payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"detail": "تم استلام الشكوى."})
        for _ in range(9):
            self.client.post("/api/complaints/public/", payload)
        response = self.client.post("/api/complaints/public/", payload)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً.")
