from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import User
from apps.complaints.models import Complaint, FollowUp
from apps.complaints.services import (
    accept_complaint,
    assign_complaint,
    close_legal,
    submit_field_report,
)
from apps.geography.models import Governorate, Region


class ComplaintServiceTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="الخليل")
        self.region = Region.objects.create(governorate=self.governorate, name="الحرم")
        self.governor = User.objects.create_user(
            username="governor", password="password-123", role=User.Role.GOVERNOR,
            governorate=self.governorate,
        )
        self.inspector = User.objects.create_user(
            username="inspector", password="password-123", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="المفتش الأول",
        )
        self.second_inspector = User.objects.create_user(
            username="other", password="password-123", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region,
        )
        self.legal = User.objects.create_user(
            username="legal", password="password-123", role=User.Role.LEGAL,
        )

    def complaint(self):
        return Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="عنوان", body="تفاصيل"
        )

    def test_second_inspector_keeps_first_assignment(self):
        complaint = self.complaint()
        accept_complaint(complaint, self.inspector, channel="web", ip="127.0.0.1", telegram_id=None)
        with self.assertRaisesMessage(ValidationError, "استلم هذه الشكوى مفتش آخر."):
            accept_complaint(complaint, self.second_inspector, channel="web", ip="127.0.0.1", telegram_id=None)
        complaint.refresh_from_db()
        self.assertEqual(complaint.inspector, self.inspector)

    def test_five_transitions(self):
        complaint = self.complaint()
        assign_complaint(complaint, self.governor, self.inspector, channel="web", ip="1", telegram_id=None)
        self.assertEqual(complaint.status, Complaint.Status.FIELD)
        submit_field_report(complaint, self.inspector, "تمت المعاينة", [], "legal")
        self.assertEqual(complaint.status, Complaint.Status.LEGAL)
        close_legal(complaint, self.legal, "", channel="web", ip="1", telegram_id=None)
        self.assertEqual(complaint.status, Complaint.Status.RESOLVED)

    def test_empty_field_text_and_sixth_file_are_rejected(self):
        complaint = self.complaint()
        accept_complaint(complaint, self.inspector, channel="web", ip="1", telegram_id=None)
        with self.assertRaises(ValidationError):
            submit_field_report(complaint, self.inspector, "", [], "governor")
        files = [SimpleUploadedFile(f"{i}.png", b"image", content_type="image/png") for i in range(6)]
        with self.assertRaises(ValidationError):
            submit_field_report(complaint, self.inspector, "نص", files, "governor")

    def test_legal_empty_notes_and_followup_are_immutable(self):
        complaint = self.complaint()
        accept_complaint(complaint, self.inspector, channel="web", ip="1", telegram_id=None)
        submit_field_report(complaint, self.inspector, "نص", [], "legal")
        close_legal(complaint, self.legal, "", channel="web", ip="1", telegram_id=None)
        line = FollowUp.objects.get(place=FollowUp.Place.LEGAL)
        self.assertEqual(line.body, "تم الانجاز")
        with self.assertRaises(ValidationError):
            line.save()
