import json

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
