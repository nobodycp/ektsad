import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from apps.accounts.models import User
from apps.field_missions.models import FieldMission
from apps.geography.models import Governorate, Region


def _png():
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("shop.png", buffer.getvalue(), content_type="image/png")


class FieldMissionApiTests(TestCase):
    def setUp(self):
        self.governorate = Governorate.objects.create(name="محافظة تجريبية")
        self.other_governorate = Governorate.objects.create(name="محافظة أخرى")
        self.region = Region.objects.create(governorate=self.governorate, name="المنطقة الأولى")
        self.other_region = Region.objects.create(governorate=self.governorate, name="المنطقة الثانية")
        self.away_region = Region.objects.create(governorate=self.other_governorate, name="منطقة بعيدة")
        self.admin = User.objects.create_user(
            username="admin", password="admin-password-12", role=User.Role.ADMIN, display_name="مدير النظام"
        )
        self.governor = User.objects.create_user(
            username="governor", password="governor-password-12", role=User.Role.GOVERNOR,
            governorate=self.governorate, display_name="مدير المحافظة",
            can_open_field_missions=True, can_view_field_missions=True,
        )
        self.inspector = User.objects.create_user(
            username="inspector", password="inspector-password-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="المفتش",
            can_open_field_missions=True, can_view_field_missions=True,
        )
        self.colleague = User.objects.create_user(
            username="colleague", password="inspector-password-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="زميل المنطقة",
            can_view_field_missions=True,
        )
        self.other_inspector = User.objects.create_user(
            username="other", password="inspector-password-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.other_region, display_name="مفتش آخر",
            can_view_field_missions=True,
        )
        self.away = User.objects.create_user(
            username="away", password="inspector-password-12", role=User.Role.INSPECTOR,
            governorate=self.other_governorate, region=self.away_region, display_name="مفتش بعيد",
            can_view_field_missions=True,
        )
        self.inactive = User.objects.create_user(
            username="inactive", password="inspector-password-12", role=User.Role.INSPECTOR,
            governorate=self.governorate, region=self.region, display_name="مفتش معطّل",
            is_active=False, can_view_field_missions=True,
        )
        self.legal = User.objects.create_user(
            username="legal", password="legal-password-12", role=User.Role.LEGAL,
            display_name="الشؤون القانونية", can_open_field_missions=True, can_view_field_missions=True,
        )

    def _open(self, user, **extra):
        self.client.force_login(user)
        payload = {"kind": "ضبط", "details": "تفاصيل المهمة", "place_name": "محل النور", "phone": "0599000000"}
        payload.update(extra)
        return self.client.post("/api/field-missions/", data=json.dumps(payload), content_type="application/json")

    def _titles(self):
        return [row["place_name"] for row in self.client.get("/api/field-missions/").json()["results"]]

    def test_view_permission_hides_the_list_and_scope_follows_role(self):
        self.client.force_login(self.inspector)
        self.inspector.can_view_field_missions = False
        self.inspector.save(update_fields=["can_view_field_missions"])
        self.assertEqual(self.client.get("/api/field-missions/").status_code, 403)

        self.inspector.can_view_field_missions = True
        self.inspector.save(update_fields=["can_view_field_missions"])
        own = self._open(self.inspector)
        self.assertEqual(own.status_code, 201)
        self.assertEqual(own.json()["assignees"], [{"id": self.inspector.pk, "name": "المفتش"}])
        self.assertEqual(own.json()["region_name"], "المنطقة الأولى")

        self.client.force_login(self.colleague)
        self.assertEqual(self._titles(), ["محل النور"])
        self.client.force_login(self.other_inspector)
        self.assertEqual(self._titles(), [])
        self.client.force_login(self.governor)
        self.assertEqual(self._titles(), ["محل النور"])
        self.client.force_login(self.admin)
        self.assertEqual(self._titles(), ["محل النور"])
        self.client.force_login(self.legal)
        self.assertEqual(self._titles(), ["محل النور"])

    def test_governor_assigns_one_or_every_active_inspector_in_the_governorate(self):
        one = self._open(self.governor, governorate=self.governorate.pk, scope="one", inspector=self.other_inspector.pk, place_name="محل واحد")
        self.assertEqual(one.status_code, 201)
        self.assertEqual(one.json()["assignees"], [{"id": self.other_inspector.pk, "name": "مفتش آخر"}])
        self.assertEqual(one.json()["region_name"], "المنطقة الثانية")

        outside = self._open(self.governor, scope="one", inspector=self.away.pk, place_name="خارج")
        self.assertEqual(outside.status_code, 400)
        self.assertEqual(outside.json()["detail"], "المفتش لا يتبع هذه المحافظة.")

        everyone = self._open(self.governor, scope="all", place_name="كل المفتشين")
        self.assertEqual(everyone.status_code, 201)
        names = {row["name"] for row in everyone.json()["assignees"]}
        self.assertEqual(names, {"المفتش", "زميل المنطقة", "مفتش آخر"})
        self.assertIsNone(everyone.json()["region"])
        self.assertEqual(FieldMission.objects.filter(place_name="كل المفتشين").count(), 1)

        self.client.force_login(self.away)
        self.assertEqual(self._titles(), [])
        self.client.force_login(self.other_inspector)
        self.assertEqual(self._titles(), ["كل المفتشين", "محل واحد"])

    def test_admin_reaches_any_governorate_and_legal_cannot_open(self):
        opened = self._open(
            self.admin, governorate=self.other_governorate.pk, scope="one", inspector=self.away.pk, place_name="بعيد"
        )
        self.assertEqual(opened.status_code, 201)
        self.client.force_login(self.governor)
        self.assertEqual(self._titles(), [])
        self.client.force_login(self.admin)
        self.assertEqual(self._titles(), ["بعيد"])

        denied = self._open(self.legal, scope="one", inspector=self.inspector.pk, governorate=self.governorate.pk)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"], "هذا الدور لا يفتح مهمة ميدانية.")

        self.governorate.users.filter(role=User.Role.INSPECTOR, is_active=True).update(is_active=False)
        empty = self._open(self.admin, governorate=self.governorate.pk, scope="all", place_name="فارغة")
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json()["detail"], "لا يوجد مفتش مفعّل في هذه المحافظة.")

    def test_required_text_and_optional_image_follow_visibility(self):
        self.client.force_login(self.inspector)
        missing = self.client.post(
            "/api/field-missions/",
            data=json.dumps({"kind": "ضبط", "details": "", "place_name": "محل", "phone": "0599"}),
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["detail"], "التفاصيل مطلوبة.")

        opened = self.client.post(
            "/api/field-missions/",
            data={
                "kind": "مصادرة",
                "details": "بضاعة",
                "place_name": "محل الصورة",
                "phone": "0568000000",
                "image": _png(),
            },
        )
        self.assertEqual(opened.status_code, 201)
        self.assertTrue(opened.json()["has_image"])
        media = self.client.get(f"/api/media/field-missions/{opened.json()['id']}/")
        self.assertEqual(media.status_code, 200)

        self.client.force_login(self.away)
        self.assertEqual(self.client.get(f"/api/media/field-missions/{opened.json()['id']}/").status_code, 404)

    def test_admin_grants_the_two_permissions(self):
        self.client.force_login(self.admin)
        response = self.client.patch(
            f"/api/users/{self.away.pk}/",
            data=json.dumps({"can_open_field_missions": True, "can_view_field_missions": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["can_open_field_missions"])
        self.assertTrue(response.json()["can_view_field_missions"])
        self.client.force_login(self.away)
        me = self.client.get("/api/auth/me/").json()
        self.assertTrue(me["can_open_field_missions"])
        self.assertTrue(me["can_view_field_missions"])
