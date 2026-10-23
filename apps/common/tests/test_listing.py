from datetime import timedelta

from django.db.models import F
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.common.listing import paginate


class ListingTests(TestCase):
    def test_page_contract_caps_page_size_and_reverses_created_at(self):
        first = User.objects.create_user(
            username="first", password="valid-password-12", role=User.Role.LEGAL
        )
        second = User.objects.create_user(
            username="second", password="valid-password-12", role=User.Role.LEGAL
        )
        User.objects.filter(pk=first.pk).update(date_joined=timezone.now() - timedelta(days=1))
        queryset = User.objects.annotate(created_at=F("date_joined"))
        body = paginate(
            queryset, {"page": "1", "page_size": "500", "ordering": "-created_at"}
        )
        self.assertEqual(set(body), {"count", "page", "page_size", "results"})
        self.assertEqual(body["page_size"], 100)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["count"], 2)
        self.assertEqual([user.pk for user in body["results"]], [second.pk, first.pk])
