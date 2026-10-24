import json

from django.contrib.sessions.models import Session
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.services import reset_password
from apps.complaints.models import Complaint, FollowUp
from apps.geography.models import Governorate, Region


class UserAdministrationTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="محافظة تجريبية")
        self.region = Region.objects.create(
            governorate=self.governorate, name="المنطقة الأولى"
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="admin-password-12",
            display_name="مدير النظام",
            role=User.Role.ADMIN,
        )
        self.inspector = User.objects.create_user(
            username="inspector",
            password="inspector-password-12",
            display_name="المفتش",
            role=User.Role.INSPECTOR,
            governorate=self.governorate,
            region=self.region,
        )

    def _sessions_for(self, user):
        return [
            session
            for session in Session.objects.all()
            if str(session.get_decoded().get("_auth_user_id")) == str(user.pk)
        ]

    def test_reset_is_sixteen_chars_and_last_admin_cannot_be_deleted(self):
        raw = reset_password(self.inspector)
        self.assertEqual(len(raw), 16)
        self.assertTrue(raw.isalnum())
        self.inspector.refresh_from_db()
        self.assertTrue(self.inspector.check_password(raw))

        self.client.force_login(self.admin)
        denied = self.client.delete(f"/api/users/{self.admin.pk}/")
        self.assertEqual(denied.status_code, 400)

    def test_reset_invalidates_target_sessions_and_admin_lists_users(self):
        self.client.force_login(self.inspector)
        self.assertTrue(self._sessions_for(self.inspector))
        self.client.force_login(self.admin)

        reset = self.client.post(
            f"/api/users/{self.inspector.pk}/password/",
            data=json.dumps({"mode": "reset"}),
            content_type="application/json",
        )
        listing = self.client.get("/api/users/", {"q": "مفتش", "role": "inspector"})

        self.assertEqual(reset.status_code, 200)
        self.assertEqual(len(reset.json()["password"]), 16)
        self.assertFalse(self._sessions_for(self.inspector))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(set(listing.json()), {"count", "page", "page_size", "results"})
        self.assertEqual(listing.json()["results"][0]["username"], "inspector")

    def test_admin_password_change_invalidates_target_sessions(self):
        self.client.force_login(self.inspector)
        self.assertTrue(self._sessions_for(self.inspector))

        self.client.force_login(self.admin)
        response = self.client.post(
            f"/api/users/{self.inspector.pk}/password/",
            data=json.dumps(
                {
                    "mode": "set",
                    "password": "new-inspector-password-12",
                    "password_confirm": "new-inspector-password-12",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._sessions_for(self.inspector))
        self.inspector.refresh_from_db()
        self.assertTrue(self.inspector.check_password("new-inspector-password-12"))

    def test_deleting_follow_up_author_keeps_author_name(self):
        complaint = Complaint.objects.create(
            governorate=self.governorate,
            region=self.region,
            title="عنوان الشكوى",
            body="نص الشكوى",
        )
        follow_up = FollowUp.objects.create(
            complaint=complaint,
            author=self.inspector,
            author_name=self.inspector.display_name,
            place=FollowUp.Place.FIELD,
            body="تفاصيل الكشف",
        )

        self.client.force_login(self.admin)
        response = self.client.delete(f"/api/users/{self.inspector.pk}/")

        self.assertEqual(response.status_code, 200)
        follow_up.refresh_from_db()
        self.assertIsNone(follow_up.author_id)
        self.assertEqual(follow_up.author_name, "المفتش")

    def test_admin_cannot_delete_self(self):
        second_admin = User.objects.create_user(
            username="admin-two",
            password="admin-two-password-12",
            role=User.Role.ADMIN,
        )
        self.client.force_login(self.admin)

        response = self.client.delete(f"/api/users/{self.admin.pk}/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "لا يمكن حذف حسابك.")
        self.assertTrue(User.objects.filter(pk=second_admin.pk).exists())

    def test_create_patch_and_bulk_actions_are_admin_only(self):
        self.client.force_login(self.admin)
        created = self.client.post(
            "/api/users/",
            data=json.dumps(
                {
                    "username": "legal",
                    "display_name": "الشؤون القانونية",
                    "password": "legal-password-12",
                    "role": "legal",
                    "governorate": None,
                    "region": None,
                    "can_publish_prices": True,
                    "can_publish_crossings": False,
                    "can_view_all_complaints": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        legal = User.objects.get(username="legal")
        self.assertNotIn("password", created.json())

        patched = self.client.patch(
            f"/api/users/{legal.pk}/",
            data=json.dumps({"username": "immutable", "display_name": "قانوني"}),
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 200)
        legal.refresh_from_db()
        self.assertEqual(legal.username, "legal")
        self.assertEqual(legal.display_name, "قانوني")

        bulk = self.client.post(
            "/api/users/actions/",
            data=json.dumps({"action": "deactivate", "ids": [legal.pk]}),
            content_type="application/json",
        )
        self.assertEqual(bulk.status_code, 200)
        legal.refresh_from_db()
        self.assertFalse(legal.is_active)

    def test_governor_lists_only_inspectors_in_the_governorate(self):
        governor = User.objects.create_user(
            username="governor", password="governor-password-12", role=User.Role.GOVERNOR,
            governorate=self.governorate, display_name="المدير",
        )
        self.client.force_login(governor)
        response = self.client.get("/api/users/", {"role": "inspector", "is_active": "1"})
        self.assertEqual(response.status_code, 200)
        usernames = [row["username"] for row in response.json()["results"]]
        self.assertEqual(usernames, ["inspector"])

    def test_login_rejects_get_and_last_admin_cannot_be_deactivated(self):
        self.assertEqual(self.client.get("/api/auth/login/").status_code, 405)

        self.client.force_login(self.admin)
        patched = self.client.patch(
            f"/api/users/{self.admin.pk}/",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        bulk = self.client.post(
            "/api/users/actions/",
            data=json.dumps({"action": "deactivate", "ids": [self.admin.pk]}),
            content_type="application/json",
        )

        self.assertEqual(patched.status_code, 400)
        self.assertEqual(patched.json()["detail"], "لا يمكن تعطيل آخر مدير نظام مفعّل.")
        self.assertEqual(bulk.json()["failed"][0]["detail"], "لا يمكن تعطيل آخر مدير نظام مفعّل.")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_enters_a_user_and_returns_to_the_same_account(self):
        self.inspector.can_login_web = False
        self.inspector.save(update_fields=["can_login_web"])
        self.client.force_login(self.admin)

        entered = self.client.post(f"/api/users/{self.inspector.pk}/enter/")
        self.assertEqual(entered.status_code, 200)
        self.assertEqual(entered.json()["username"], "inspector")
        self.assertEqual(entered.json()["impersonator"]["username"], "admin")
        self.assertEqual(self.client.get("/api/auth/me/").json()["role"], "inspector")
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/users/{self.admin.pk}/enter/").status_code, 403)

        back = self.client.post("/api/auth/return/")
        self.assertEqual(back.status_code, 200)
        self.assertEqual(back.json()["username"], "admin")
        self.assertIsNone(back.json()["impersonator"])
        self.assertEqual(self.client.get("/api/users/").status_code, 200)

    def test_enter_refuses_self_inactive_and_non_admin(self):
        self.client.force_login(self.inspector)
        self.assertEqual(self.client.post(f"/api/users/{self.admin.pk}/enter/").status_code, 403)

        self.client.force_login(self.admin)
        own = self.client.post(f"/api/users/{self.admin.pk}/enter/")
        self.assertEqual(own.status_code, 400)
        self.assertEqual(own.json()["detail"], "لا يمكن الدخول بحسابك.")
        self.inspector.is_active = False
        self.inspector.save(update_fields=["is_active"])
        inactive = self.client.post(f"/api/users/{self.inspector.pk}/enter/")
        self.assertEqual(inactive.status_code, 400)
        self.assertEqual(inactive.json()["detail"], "لا يمكن الدخول بحساب معطّل.")
        self.assertEqual(self.client.post("/api/users/99999/enter/").status_code, 404)
        self.assertEqual(self.client.post("/api/auth/return/").status_code, 400)

    def test_return_logs_out_when_the_admin_was_disabled(self):
        other = User.objects.create_user(
            username="admin-2", password="admin-password-12", role=User.Role.ADMIN
        )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(f"/api/users/{self.inspector.pk}/enter/").status_code, 200)
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        response = self.client.post("/api/auth/return/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "تعذّرت العودة إلى حساب المدير.")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)
        self.assertTrue(other.is_active)
