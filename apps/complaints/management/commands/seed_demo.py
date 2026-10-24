from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.complaints.models import Complaint, FollowUp
from apps.geography.models import Region

MARKER = "تجريبي:"


class Command(BaseCommand):
    help = "Seed demo complaints so overview charts have numbers. Safe to run again."

    def handle(self, *args, **options):
        if Complaint.objects.filter(title__startswith=MARKER).exists():
            self.stdout.write("بيانات العرض موجودة.")
            return
        region = Region.objects.select_related("governorate").first()
        inspector = User.objects.filter(role=User.Role.INSPECTOR).first()
        governor = User.objects.filter(role=User.Role.GOVERNOR).first()
        legal = User.objects.filter(role=User.Role.LEGAL).first()
        if region is None or inspector is None:
            self.stderr.write("أنشئ الجغرافيا والمفتش أولاً.")
            return
        now = timezone.now()
        samples = [
            ("سعر الخبز", Complaint.Status.RECEIVED, None),
            ("نقص في الميزان", Complaint.Status.RECEIVED, None),
            ("إعلان مضلل", Complaint.Status.RECEIVED, None),
            ("محل بلا تسعيرة", Complaint.Status.FIELD, inspector),
            ("مادة منتهية", Complaint.Status.FIELD, inspector),
            ("فاتورة غير واضحة", Complaint.Status.FINISHED, inspector),
            ("زيادة غير معلنة", Complaint.Status.FINISHED, inspector),
            ("شكوى عقد", Complaint.Status.LEGAL, inspector),
            ("تم إغلاق ملف", Complaint.Status.RESOLVED, inspector),
        ]
        for title, status, owner in samples:
            complaint = Complaint.objects.create(
                governorate=region.governorate,
                region=region,
                title=f"{MARKER} {title}",
                body="بيانات للعرض فقط.",
                status=status,
                inspector=owner,
                inspector_name=owner.display_name if owner else "",
                assigned_by=governor if owner else None,
                assigned_by_name=governor.display_name if owner and governor else "",
                accepted_at=now if owner else None,
                source=Complaint.Source.WEB,
            )
            if status == Complaint.Status.FINISHED:
                complaint.closed_at = now
                complaint.save(update_fields=["closed_at"])
                FollowUp.objects.create(
                    complaint=complaint,
                    author=inspector,
                    author_name=inspector.display_name,
                    place=FollowUp.Place.FIELD,
                    body="تمت المتابعة.",
                )
            if status == Complaint.Status.LEGAL:
                complaint.legal_referred_at = now
                complaint.save(update_fields=["legal_referred_at"])
            if status == Complaint.Status.RESOLVED and legal:
                complaint.closed_at = now
                complaint.legal_referred_at = now
                complaint.save(update_fields=["closed_at", "legal_referred_at"])
                FollowUp.objects.create(
                    complaint=complaint,
                    author=legal,
                    author_name=legal.display_name,
                    place=FollowUp.Place.LEGAL,
                    body="تم الانجاز",
                )
        self.stdout.write(f"أُضيفت {len(samples)} شكاوى للعرض.")
