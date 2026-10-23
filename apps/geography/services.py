from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from apps.geography.models import Governorate, Region


DELETE_GUARD_MESSAGE = "لا يمكن حذف سجل مرتبط."


def delete_governorate(pk):
    governorate = Governorate.objects.get(pk=pk)
    if governorate.regions.exists():
        raise ValidationError(DELETE_GUARD_MESSAGE)
    try:
        governorate.delete()
    except ProtectedError as error:
        raise ValidationError(DELETE_GUARD_MESSAGE) from error


def delete_region(pk):
    region = Region.objects.get(pk=pk)
    try:
        region.delete()
    except ProtectedError as error:
        raise ValidationError(DELETE_GUARD_MESSAGE) from error
