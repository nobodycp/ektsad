from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import StaffRole, User
from apps.complaints.models import Complaint, FollowUp
from apps.field_missions.models import FieldMission, FieldMissionAssignee, FieldMissionFollowUp
from apps.geography.models import Governorate, Region

MARKER = "استعراض"
PASSWORD = "preview-password-12"


class Command(BaseCommand):
    help = "أرقام استعراض للبوت: مفتشون ومدراء وشكاوى ومهمات مفتوحة ومغلقة ومحوّلة."

    def handle(self, *args, **options):
        now = timezone.now()
        self._mission_permissions()
        places = self._places()
        if places is None:
            return
        people = self._people(places)
        complaints = self._complaints(now, people)
        missions = self._missions(now, people)
        self.stdout.write(f"الشكاوى الجديدة: {complaints}. المهمات الجديدة: {missions}.")
        self.stdout.write("الحسابات الجديدة كلمة مرورها preview-password-12. اربط كل حساب من صفحة المستخدمين قبل الاستعراض على البوت.")

    def _mission_permissions(self):
        StaffRole.objects.filter(built_in=True, kind=StaffRole.Kind.INSPECTOR).update(
            can_view_field_missions=True,
        )
        StaffRole.objects.filter(built_in=True, kind=StaffRole.Kind.GOVERNOR).update(
            can_view_field_missions=True, can_open_field_missions=True,
        )
        StaffRole.objects.filter(built_in=True, kind=StaffRole.Kind.LEGAL).update(
            can_view_field_missions=True,
        )

    def _places(self):
        first = Governorate.objects.order_by("pk").first()
        second = Governorate.objects.order_by("pk")[1:2].first() or first
        if first is None:
            self.stderr.write("لا توجد محافظة.")
            return None
        regions = list(Region.objects.filter(governorate=first).order_by("pk")[:2])
        if len(regions) < 2:
            self.stderr.write("يلزم منطقتان في المحافظة الأولى.")
            return None
        other = Region.objects.filter(governorate=second).order_by("pk").first() or regions[0]
        return {"first": first, "second": second, "a": regions[0], "b": regions[1], "c": other}

    def _people(self, places):
        roles = {role.kind: role for role in StaffRole.objects.filter(built_in=True)}
        specs = [
            ("preview-governor", "مدير الاستعراض", User.Role.GOVERNOR, places["first"], None, StaffRole.Kind.GOVERNOR),
            ("preview-governor-2", "مدير الاستعراض الثاني", User.Role.GOVERNOR, places["second"], None, StaffRole.Kind.GOVERNOR),
            ("preview-inspector-a", "مفتش الاستعراض أ", User.Role.INSPECTOR, places["first"], places["a"], StaffRole.Kind.INSPECTOR),
            ("preview-inspector-b", "مفتش الاستعراض ب", User.Role.INSPECTOR, places["first"], places["b"], StaffRole.Kind.INSPECTOR),
            ("preview-inspector-c", "مفتش الاستعراض ج", User.Role.INSPECTOR, places["second"], places["c"], StaffRole.Kind.INSPECTOR),
            ("preview-legal", "قانوني الاستعراض", User.Role.LEGAL, None, None, StaffRole.Kind.LEGAL),
        ]
        people = {}
        for username, name, role, governorate, region, kind in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "display_name": name,
                    "role": role,
                    "governorate": governorate,
                    "region": region,
                    "staff_role": roles.get(kind),
                    "is_active": True,
                },
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
            people[username] = user
        return people

    def _complaints(self, now, people):
        if Complaint.objects.filter(title__startswith=f"{MARKER}:").exists():
            return 0
        governor = people["preview-governor"]
        inspector_a = people["preview-inspector-a"]
        inspector_b = people["preview-inspector-b"]
        legal = people["preview-legal"]
        rows = [
            ("محل بلا تسعيرة", "واردة في المنطقة الأولى.", inspector_a, Complaint.Status.RECEIVED, None),
            ("إعلان مضلل", "شكوى مفتوحة بانتظار القبول.", inspector_a, Complaint.Status.RECEIVED, None),
            ("نقص في الميزان", "واردة في المنطقة الثانية.", inspector_b, Complaint.Status.RECEIVED, None),
            ("سعر مرتفع", "قيد الكشف عند مفتش الاستعراض أ.", inspector_a, Complaint.Status.FIELD, inspector_a),
            ("مادة منتهية", "كشف ميداني مفتوح.", inspector_a, Complaint.Status.FIELD, inspector_a),
            ("فاتورة ناقصة", "كشف ميداني في المنطقة الثانية.", inspector_b, Complaint.Status.FIELD, inspector_b),
            ("عقد غير واضح", "أُحيلت للشؤون القانونية.", inspector_a, Complaint.Status.LEGAL, inspector_a),
            ("رفض الاستبدال", "محوّلة للمتابعة القانونية.", inspector_b, Complaint.Status.LEGAL, inspector_b),
            ("زيادة غير معلنة", "أُغلقت عند مدير المحافظة.", inspector_a, Complaint.Status.FINISHED, inspector_a),
            ("عرض ناقص", "منتهية بعد الكشف.", inspector_b, Complaint.Status.FINISHED, inspector_b),
            ("تم إغلاق الملف", "أُنجزت في الشؤون القانونية.", inspector_a, Complaint.Status.RESOLVED, inspector_a),
        ]
        for title, body, region_user, status, owner in rows:
            complaint = Complaint.objects.create(
                governorate=region_user.governorate,
                region=region_user.region,
                title=f"{MARKER}: {title}",
                body=body,
                status=status,
                inspector=owner,
                inspector_name=(owner.display_name if owner else ""),
                assigned_by=governor if owner else None,
                assigned_by_name=governor.display_name if owner else "",
                accepted_at=now if owner else None,
                source=Complaint.Source.WEB,
            )
            if status == Complaint.Status.FINISHED:
                complaint.closed_at = now
                complaint.save(update_fields=["closed_at"])
                FollowUp.objects.create(
                    complaint=complaint, author=owner, author_name=owner.display_name,
                    place=FollowUp.Place.FIELD, body="أُغلق الكشف عند مدير المحافظة.",
                )
            if status == Complaint.Status.LEGAL:
                complaint.legal_referred_at = now
                complaint.save(update_fields=["legal_referred_at"])
                FollowUp.objects.create(
                    complaint=complaint, author=owner, author_name=owner.display_name,
                    place=FollowUp.Place.FIELD, body="أُحيلت إلى الشؤون القانونية.",
                )
            if status == Complaint.Status.RESOLVED:
                complaint.closed_at = now
                complaint.legal_referred_at = now
                complaint.save(update_fields=["closed_at", "legal_referred_at"])
                FollowUp.objects.create(
                    complaint=complaint, author=legal, author_name=legal.display_name,
                    place=FollowUp.Place.LEGAL, body="تم الانجاز.",
                )
        return len(rows)

    def _missions(self, now, people):
        if FieldMission.objects.filter(place_name__startswith=f"{MARKER}:").exists():
            return 0
        governor = people["preview-governor"]
        inspector_a = people["preview-inspector-a"]
        inspector_b = people["preview-inspector-b"]
        rows = [
            ("البقالة", FieldMission.Kind.SEIZURE, FieldMission.Status.FIELD, inspector_a, "مهمة مفتوحة للضبط."),
            ("المخبز", FieldMission.Kind.STATUS, FieldMission.Status.FIELD, inspector_a, "إثبات حالة قيد المتابعة."),
            ("السوق", FieldMission.Kind.HOLD, FieldMission.Status.FIELD, inspector_b, "تحفظ مفتوح في المنطقة الثانية."),
            ("المستودع", FieldMission.Kind.SAMPLES, FieldMission.Status.LEGAL, inspector_a, "محوّلة للشؤون القانونية."),
            ("المحل التجاري", FieldMission.Kind.OTHER, FieldMission.Status.LEGAL, inspector_b, "بانتظار القانوني."),
            ("الكافتيريا", FieldMission.Kind.DESTRUCTION, FieldMission.Status.FINISHED, inspector_a, "مهمة منتهية."),
            ("الصيدلية", FieldMission.Kind.CONFISCATION, FieldMission.Status.RESOLVED, inspector_a, "تمت المعالجة."),
        ]
        for place, kind, status, inspector, details in rows:
            mission = FieldMission.objects.create(
                kind=kind,
                priority=FieldMission.Priority.NORMAL,
                status=status,
                details=details,
                place_name=f"{MARKER}: {place}",
                phone="0599000000",
                governorate=inspector.governorate,
                region=inspector.region,
                created_by=governor,
                created_by_name=governor.display_name,
                field_replied_at=now if status != FieldMission.Status.FIELD else None,
                legal_referred_at=now if status in {FieldMission.Status.LEGAL, FieldMission.Status.RESOLVED} else None,
                closed_at=now if status in {FieldMission.Status.FINISHED, FieldMission.Status.RESOLVED} else None,
            )
            FieldMissionAssignee.objects.create(
                mission=mission, user=inspector, display_name=inspector.display_name,
            )
            if status != FieldMission.Status.FIELD:
                FieldMissionFollowUp.objects.create(
                    mission=mission, author=inspector, author_name=inspector.display_name,
                    place=FieldMissionFollowUp.Place.FIELD, body=details,
                )
        return len(rows)
