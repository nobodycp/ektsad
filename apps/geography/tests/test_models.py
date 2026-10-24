from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.geography.models import Governorate, Region
from apps.geography.services import delete_governorate, delete_region


class GeographyModelTests(TestCase):
    def test_duplicate_region_name_in_one_governorate_rejected(self):
        governorate = Governorate.objects.create(name="محافظة تجريبية")
        Region.objects.create(governorate=governorate, name="المنطقة الأولى")
        with self.assertRaises(IntegrityError):
            Region.objects.create(governorate=governorate, name="المنطقة الأولى")

    def test_delete_governorate_with_region_is_rejected(self):
        governorate = Governorate.objects.create(name="محافظة تجريبية")
        Region.objects.create(governorate=governorate, name="المنطقة الأولى")
        with self.assertRaisesMessage(ValidationError, "لا يمكن حذف سجل مرتبط."):
            delete_governorate(governorate.pk)

    def test_duplicate_name_is_an_arabic_400_and_linked_delete_is_refused(self):
        admin = User.objects.create_user(username="admin", password="valid-password-12", role=User.Role.ADMIN)
        governorate = Governorate.objects.create(name="محافظة تجريبية")
        Region.objects.create(governorate=governorate, name="المنطقة الأولى")
        self.client.force_login(admin)
        duplicate = self.client.post(
            "/api/governorates/", data='{"name": "محافظة تجريبية"}', content_type="application/json"
        )
        denied = self.client.delete(f"/api/governorates/{governorate.pk}/")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["detail"], "الاسم مستخدم.")
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(denied.json()["detail"], "لا يمكن حذف سجل مرتبط.")

    def test_delete_region_without_references_succeeds(self):
        governorate = Governorate.objects.create(name="محافظة تجريبية")
        region = Region.objects.create(governorate=governorate, name="المنطقة الأولى")
        delete_region(region.pk)
        self.assertFalse(Region.objects.filter(pk=region.pk).exists())
