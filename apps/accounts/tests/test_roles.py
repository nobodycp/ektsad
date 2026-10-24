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
        self.assertEqual(set(names), {"مدير المحافظة", "مفتش", "الشؤون القانونية"})
        governor = names["مدير المحافظة"]

        renamed = self.client.patch(
            f"/api/roles/{governor['id']}/",
            data=json.dumps({"name": "مدير المديرية", "can_field_missions": True}),
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "مدير المديرية")
        self.assertTrue(renamed.json()["can_field_missions"])
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
