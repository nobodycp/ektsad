from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

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

    def test_delete_region_without_references_succeeds(self):
        governorate = Governorate.objects.create(name="محافظة تجريبية")
        region = Region.objects.create(governorate=governorate, name="المنطقة الأولى")
        delete_region(region.pk)
        self.assertFalse(Region.objects.filter(pk=region.pk).exists())
