from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import User
from apps.complaints.models import Complaint, FollowUp
from apps.geography.models import Governorate, Region
from apps.publications.models import CrossingReport, PriceReport
from apps.reports.queries import admin_report, governor_daily


HEBRON = ZoneInfo("Asia/Hebron")


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=HEBRON)


class ReportTests(TestCase):
    def setUp(self):
        self.day = date(2026, 10, 24)
        self.previous_day = date(2026, 10, 23)
        self.governorate = Governorate.objects.create(name="الخليل")
        self.region = Region.objects.create(governorate=self.governorate, name="الحرم")
        self.other_governorate = Governorate.objects.create(name="رام الله")
        self.other_region = Region.objects.create(governorate=self.other_governorate, name="المدينة")
        self.admin = User.objects.create_user(
            username="admin", password="password-12345", role=User.Role.ADMIN, display_name="مدير النظام"
        )
        self.governor = User.objects.create_user(
            username="governor", password="password-12345", role=User.Role.GOVERNOR,
            governorate=self.governorate,
        )
        self.inspector = User.objects.create_user(
            username="inspector", password="password-12345", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="المفتش الأول",
        )
        self.legal = User.objects.create_user(
            username="legal", password="password-12345", role=User.Role.LEGAL
        )

    def complaint(self, *, status=Complaint.Status.RECEIVED, accepted_at=None, closed_at=None,
                  legal_referred_at=None, created_at=None):
        complaint = Complaint.objects.create(
            governorate=self.governorate, region=self.region, title="عنوان", body="تفاصيل",
            status=status, inspector=self.inspector if accepted_at else None,
            inspector_name=self.inspector.display_name if accepted_at else "",
        )
        Complaint.objects.filter(pk=complaint.pk).update(
            accepted_at=accepted_at, closed_at=closed_at, legal_referred_at=legal_referred_at,
            created_at=created_at or at(self.day, 9),
        )
        complaint.refresh_from_db()
        return complaint

    def field_followup(self, complaint, created_at):
        followup = FollowUp.objects.create(
            complaint=complaint, author=self.inspector, author_name=self.inspector.display_name,
            place=FollowUp.Place.FIELD, body="تمت المعاينة",
        )
        FollowUp.objects.filter(pk=followup.pk).update(created_at=created_at)

    def test_same_day_close_is_done_not_pending(self):
        complaint = self.complaint(
            status=Complaint.Status.FINISHED, accepted_at=at(self.day, 9), closed_at=at(self.day, 15)
        )
        self.field_followup(complaint, at(self.day, 14))

        report = governor_daily(self.governorate, self.day)

        self.assertEqual(report["done"], 1)
        self.assertEqual(report["pending"], 0)
        self.assertEqual(report["done_by_inspector"][self.inspector.display_name], 1)

    def test_legal_still_open_is_pending_but_unaccepted_received_is_not(self):
        self.complaint(
            status=Complaint.Status.LEGAL, accepted_at=at(self.day, 8), legal_referred_at=at(self.day, 10)
        )
        self.complaint(status=Complaint.Status.RECEIVED)

        report = governor_daily(self.governorate, self.day)

        self.assertEqual(report["pending"], 1)

    def test_admin_rejects_reversed_date_range_with_exact_arabic_message(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            "/api/reports/", {"date_from": "2026-10-25", "date_to": "2026-10-24"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "تاريخ البداية بعد تاريخ النهاية."})

    def test_admin_average_is_hours_minutes_or_null(self):
        first = self.complaint(accepted_at=at(self.day, 8), created_at=at(self.day, 8))
        second = self.complaint(accepted_at=at(self.day, 9), created_at=at(self.day, 9))
        self.field_followup(first, at(self.day, 10, 30))
        self.field_followup(second, at(self.day, 12, 30))

        report = admin_report({"date_from": "2026-10-24", "date_to": "2026-10-24"})

        inspector = report["inspectors"][0]
        self.assertEqual(inspector["average"], {"hours": 3, "minutes": 0})
        self.assertIsNone(
            admin_report(
                {"date_from": "2026-10-23", "date_to": "2026-10-23", "inspector": self.inspector.pk}
            )["inspectors"][0]["average"]
        )

    def test_publications_change_only_with_date_range_not_status(self):
        price = PriceReport.objects.create(
            image=SimpleUploadedFile("price.png", b"image", content_type="image/png")
        )
        crossing = CrossingReport.objects.create(body="مفتوح")
        PriceReport.objects.filter(pk=price.pk).update(published_at=at(self.previous_day, 12))
        CrossingReport.objects.filter(pk=crossing.pk).update(published_at=at(self.day, 12))

        all_days = admin_report({"date_from": "2026-10-23", "date_to": "2026-10-24"})
        filtered_status = admin_report(
            {"date_from": "2026-10-23", "date_to": "2026-10-24", "status": Complaint.Status.FINISHED}
        )
        today_only = admin_report({"date_from": "2026-10-24", "date_to": "2026-10-24"})

        self.assertEqual(all_days["publications"], {"prices": 1, "crossings": 1})
        self.assertEqual(filtered_status["publications"], all_days["publications"])
        self.assertEqual(today_only["publications"], {"prices": 0, "crossings": 1})

    def test_report_routes_enforce_roles_and_governorate_scope(self):
        self.client.force_login(self.governor)
        self.assertEqual(self.client.get("/api/governor/report/").status_code, 200)
        self.assertEqual(self.client.get("/api/reports/").status_code, 403)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/api/governor/report/").status_code, 400)
        self.assertEqual(
            self.client.get("/api/governor/report/", {"governorate": self.governorate.pk}).status_code, 200
        )

        self.client.force_login(self.legal)
        self.assertEqual(self.client.get("/api/governor/report/").status_code, 403)
        self.assertEqual(self.client.get("/api/reports/").status_code, 403)

    def test_legal_case_closed_later_stays_open_at_the_earlier_day(self):
        self.complaint(
            status=Complaint.Status.RESOLVED,
            accepted_at=at(self.previous_day, 9),
            legal_referred_at=at(self.previous_day, 11),
            closed_at=at(self.day, 10),
            created_at=at(self.previous_day, 8),
        )

        earlier = admin_report({"date_from": "2026-10-23", "date_to": "2026-10-23"})
        closed_day = admin_report({"date_from": "2026-10-24", "date_to": "2026-10-24"})

        self.assertEqual(earlier["legal"]["still_legal"], 1)
        self.assertEqual(earlier["legal"]["resolved"], 0)
        self.assertEqual(closed_day["legal"]["still_legal"], 0)
        self.assertEqual(closed_day["legal"]["resolved"], 1)

    def test_non_numeric_ids_return_arabic_400(self):
        self.client.force_login(self.admin)

        governorate = self.client.get("/api/governor/report/", {"governorate": "abc"})
        inspector = self.client.get("/api/reports/", {"inspector": "abc"})
        region = self.client.get("/api/reports/", {"region": "abc"})

        self.assertEqual(governorate.status_code, 400)
        self.assertEqual(governorate.json()["detail"], "المحافظة غير صالحة.")
        self.assertEqual(inspector.json()["detail"], "المفتش غير صالح.")
        self.assertEqual(region.json()["detail"], "المنطقة غير صالحة.")

    def test_admin_rejects_region_from_another_governorate(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            "/api/reports/",
            {"governorate": self.governorate.pk, "region": self.other_region.pk},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "المنطقة لا تتبع المحافظة."})
