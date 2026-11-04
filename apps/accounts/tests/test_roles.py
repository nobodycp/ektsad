import json

from django.test import TestCase

from apps.accounts.models import StaffRole, User
from apps.geography.models import Governorate, Region


class StaffRoleApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="admin-password-12", role=User.Role.ADMIN)
        self.client.force_login(self.admin)

    def test_builtin_roles_can_be_renamed_and_a_custom_role_grants_part_of_the_admin(self):
        listed = self.client.get("/api/roles/")
        self.assertEqual(listed.status_code, 200)
        names = {row["name"]: row for row in listed.json()["results"]}
        self.assertEqual(set(names), {
            "مدير المحافظة", "مفتش", "الشؤون القانونية", "موظف المعابر", "موظف الأسعار",
            "مدير المحافظات", "إداري المحافظة",
        })
        director = names["مدير المحافظات"]
        self.assertTrue(director["can_view_all_complaints"])
        self.assertTrue(director["can_view_reports"])
        self.assertTrue(director["can_view_field_missions"])
        self.assertTrue(director["can_open_field_missions"])
        self.assertFalse(director["can_publish_prices"])
        self.assertFalse(director["can_publish_crossings"])
        self.assertTrue(names["موظف المعابر"]["can_publish_crossings"])
        self.assertFalse(names["موظف المعابر"]["can_publish_prices"])
        self.assertTrue(names["موظف الأسعار"]["can_publish_prices"])
        self.assertFalse(names["موظف الأسعار"]["can_publish_crossings"])
        governor = names["مدير المحافظة"]

        renamed = self.client.patch(
            f"/api/roles/{governor['id']}/",
            data=json.dumps({"name": "مدير المديرية", "can_field_missions": True}),
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "مدير المديرية")
        self.assertTrue(renamed.json()["can_field_missions"])
        self.assertTrue(renamed.json()["can_view_field_missions"])
        self.assertTrue(renamed.json()["can_open_field_missions"])
        self.assertTrue(renamed.json()["built_in"])

        refused = self.client.delete(f"/api/roles/{governor['id']}/")
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.json()["detail"], "لا يمكن حذف هذا الدور.")

        created = self.client.post(
            "/api/roles/",
            data=json.dumps({"name": "مساعد المدير", "can_manage_users": True, "can_view_reports": True}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["kind"], "custom")
        self.assertFalse(created.json()["can_manage_settings"])

        place = Governorate.objects.create(name="غزة")
        region = Region.objects.create(governorate=place, name="الرمال")
        account = self.client.post(
            "/api/users/",
            data=json.dumps({
                "username": "deputy",
                "display_name": "المساعد",
                "password": "deputy-password-12",
                "role_id": created.json()["id"],
            }),
            content_type="application/json",
        )
        self.assertEqual(account.status_code, 201)
        self.assertEqual(account.json()["role"], "custom")
        self.assertEqual(account.json()["role_name"], "مساعد المدير")
        self.assertIsNone(account.json()["governorate"])

        deputy = User.objects.get(username="deputy")
        self.client.force_login(deputy)
        self.assertEqual(self.client.get("/api/users/").status_code, 200)
        self.assertEqual(self.client.get("/api/roles/").status_code, 200)
        self.assertEqual(self.client.post("/api/roles/", data=json.dumps({"name": "ممنوع"}), content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get("/api/system-settings/").status_code, 403)
        me = self.client.get("/api/auth/me/").json()
        self.assertTrue(me["can_manage_users"])
        self.assertTrue(me["can_view_reports"])
        self.assertFalse(me["can_manage_settings"])
        self.assertFalse(me["can_impersonate"])

        self.client.force_login(self.admin)
        busy = self.client.delete(f"/api/roles/{created.json()['id']}/")
        self.assertEqual(busy.status_code, 400)
        self.assertEqual(busy.json()["detail"], "هذا الدور مرتبط بمستخدمين.")
        deputy.staff_role = None
        deputy.role = User.Role.INSPECTOR
        deputy.governorate = place
        deputy.region = region
        deputy.save()
        gone = self.client.delete(f"/api/roles/{created.json()['id']}/")
        self.assertEqual(gone.status_code, 200)

    def test_each_publisher_sees_only_their_two_buttons(self):
        from apps.telegram.buttons import rows_for

        crossings_role = StaffRole.objects.get(name="موظف المعابر")
        prices_role = StaffRole.objects.get(name="موظف الأسعار")
        crossings = User.objects.create_user(
            username="crossings", password="password-long-12", role=crossings_role.kind, staff_role=crossings_role,
        )
        prices = User.objects.create_user(
            username="prices", password="password-long-12", role=prices_role.kind, staff_role=prices_role,
        )
        self.assertEqual(
            [[button["text"] for button in row] for row in rows_for(crossings)],
            [["إدخال تقرير"], ["سجل الحركات"]],
        )
        self.assertEqual(
            [[button["text"] for button in row] for row in rows_for(prices)],
            [["نشر الأسعار"], ["سجل الأسعار"]],
        )
        from apps.common.models import SystemSettings
        row = SystemSettings.current()
        row.linked_bulletin_buttons = True
        row.save(update_fields=["linked_bulletin_buttons"])
        self.assertEqual(rows_for(crossings)[-1][0]["text"], "حركة المعابر")
        self.assertEqual(rows_for(prices)[-1][0]["text"], "القائمة الاسترشادية")

    def test_governors_director_sees_every_governorate(self):
        from apps.complaints.models import Complaint
        from apps.complaints.services import visible_complaints
        from apps.telegram.buttons import rows_for

        role = StaffRole.objects.get(name="مدير المحافظات")
        director = User.objects.create_user(
            username="directors", password="password-long-12", role=role.kind, staff_role=role,
        )
        first = Governorate.objects.create(name="غزة")
        second = Governorate.objects.create(name="الشمال")
        first_region = Region.objects.create(governorate=first, name="الرمال")
        second_region = Region.objects.create(governorate=second, name="جباليا")
        Complaint.objects.create(governorate=first, region=first_region, title="الأولى", body="نص")
        Complaint.objects.create(governorate=second, region=second_region, title="الثانية", body="نص")
        self.assertEqual(set(visible_complaints(director).values_list("title", flat=True)), {"الأولى", "الثانية"})
        labels = [button["text"] for row in rows_for(director) for button in row]
        for name in ("الشكاوى", "المهمات", "إنشاء مهمة", "التقارير"):
            self.assertIn(name, labels)
        self.assertNotIn("إدخال تقرير", labels)
        self.assertNotIn("نشر الأسعار", labels)
        from django.utils import timezone
        from apps.reports.queries import _today, telegram_summary
        from apps.telegram.office import _report_text

        gaza_inspector = User.objects.create_user(
            username="gaza-inspector", password="password-long-12", role=User.Role.INSPECTOR,
            governorate=first, region=first_region, display_name="مفتش غزة",
        )
        north_inspector = User.objects.create_user(
            username="north-inspector", password="password-long-12", role=User.Role.INSPECTOR,
            governorate=second, region=second_region, display_name="مفتش الشمال",
        )
        now = timezone.now()
        Complaint.objects.filter(title="الأولى").update(
            status=Complaint.Status.FIELD, inspector=gaza_inspector, accepted_at=now,
        )
        Complaint.objects.filter(title="الثانية").update(
            status=Complaint.Status.FINISHED, inspector=north_inspector, accepted_at=now, closed_at=now,
        )
        today = _today()
        summary = telegram_summary(director, today, today)
        text = _report_text("اليوم", summary)
        self.assertLess(text.index("الشمال:"), text.index("مفتش الشمال"))
        self.assertLess(text.index("مفتش الشمال"), text.index("غزة:"))
        self.assertLess(text.index("غزة:"), text.index("مفتش غزة"))
        self.assertIn("غزة: جديدة 1، منجزة 0، معلقة 1", text)
        self.assertIn("الشمال: جديدة 1، منجزة 1، معلقة 0", text)
        self.assertNotIn("المفتشون", text)

    def test_governorate_officer_follows_only_his_inspectors(self):
        from apps.complaints.models import Complaint
        from apps.complaints.services import visible_complaints
        from apps.field_missions.models import FieldMission, FieldMissionAssignee
        from apps.field_missions.services import visible_missions
        from apps.telegram.buttons import rows_for

        role = StaffRole.objects.get(name="إداري المحافظة")
        first = Governorate.objects.create(name="غزة")
        second = Governorate.objects.create(name="الشمال")
        first_region = Region.objects.create(governorate=first, name="الرمال")
        second_region = Region.objects.create(governorate=second, name="جباليا")
        officer = User.objects.create_user(
            username="officer", password="password-long-12", role=role.kind, staff_role=role, governorate=first,
        )
        officer.full_clean()
        inspector = User.objects.create_user(
            username="field", password="password-long-12", role=User.Role.INSPECTOR,
            governorate=first, region=first_region, display_name="المفتش أحمد",
        )
        own = Complaint.objects.create(
            governorate=first, region=first_region, title="داخل المحافظة", body="نص",
            inspector=inspector, inspector_name="المفتش أحمد", status=Complaint.Status.FIELD,
        )
        Complaint.objects.create(governorate=second, region=second_region, title="خارج المحافظة", body="نص")
        self.assertEqual(list(visible_complaints(officer).values_list("title", flat=True)), ["داخل المحافظة"])
        mission = FieldMission.objects.create(
            kind=FieldMission.Kind.STATUS, priority=FieldMission.Priority.NORMAL,
            details="كشف", place_name="محل الرمال", phone="0599000000", governorate=first, region=first_region,
        )
        FieldMissionAssignee.objects.create(mission=mission, user=inspector, display_name="المفتش أحمد")
        FieldMission.objects.create(
            kind=FieldMission.Kind.STATUS, priority=FieldMission.Priority.NORMAL,
            details="كشف", place_name="محل الشمال", phone="0599000001", governorate=second, region=second_region,
        )
        self.assertEqual(list(visible_missions(officer).values_list("place_name", flat=True)), ["محل الرمال"])
        labels = [button["text"] for row in rows_for(officer) for button in row]
        for name in ("الشكاوى", "المهمات", "التقارير"):
            self.assertIn(name, labels)
        self.assertNotIn("إنشاء مهمة", labels)
        self.assertNotIn("إدخال تقرير", labels)
        from apps.complaints.models import FollowUp
        from apps.field_missions.models import FieldMissionFollowUp
        from apps.reports.queries import _today, telegram_summary
        from apps.telegram.office import _mission_text
        from apps.telegram.webhook import _complaint_card
        FollowUp.objects.create(
            complaint=own, author=inspector, author_name="المفتش أحمد",
            place=FollowUp.Place.FIELD, body="المحل مخالف",
        )
        FieldMissionFollowUp.objects.create(
            mission=mission, author=inspector, author_name="المفتش أحمد",
            place=FieldMissionFollowUp.Place.FIELD, body="أُثبتت الحالة",
        )
        self.assertIn("المفتش: المفتش أحمد", _complaint_card(own))
        self.assertIn("نتيجة الكشف: المحل مخالف", _complaint_card(own))
        self.assertIn("المفتش: المفتش أحمد", _mission_text(mission))
        self.assertIn("نتيجة الكشف: أُثبتت الحالة", _mission_text(mission))
        today = _today()
        summary = telegram_summary(officer, today, today)
        self.assertIn("المفتش أحمد: بيده 2، أنجز 0", summary["inspectors"])
