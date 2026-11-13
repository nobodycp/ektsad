from django.test import TestCase

from apps.accounts.models import User
from apps.publications.crossing_text import apply_correction, parse_crossing, present
from apps.publications.models import CrossingReport
from apps.telegram.models import TelegramDraft, TelegramLink, TelegramOutbox
from apps.telegram.office import _ask_crossing, consume_text, handle_callback

SAMPLE = """حركة الشاحنات الواردة من المعابر ليوم الأحد الموافق 01/11/2026 كانت على النحو التالي:
المعابر:
1️⃣ كرم ابوسالم
تجاري: 144شاحنة
مساعدات:66شاحنة
المحروقات:
تجاري:
سولار 0شاحنة
بنزين 0 شاحنة
غاز 0شاحنات
🎁 مؤسسات:
سولار 11شاحنة
بنزين 0شاحنة
غاز 0شاحنة
2️⃣ كيسوفيم
تجاري: 0شاحنة
مساعدات:0شاحنة
3️⃣ زكيم
تجاري: 0شاحنة
مساعدات:0شاحنة
الاجمالي العام:
تجاري 144شاحنة
مساعدات 66شاحنة
محروقات 11شاحنة
تفاصيل الشاحنات التجارية حسب الصنف:
27 مجمدات
22 خضروات
20 منظفات
19 فواكة
13 فحم
11 ملابس
7 بيض
5 دقيق و قمح
4 مواد غذائية
4 حفاظات تواليت
4 احذيه
2 مسليات و مكسرات
2 حمضيات
1 نايلون
2 حصائر
1 البان و اجبان
تفاصيل المساعدات حسب المؤسسات:
الفارس الشهم
خيام 1
دقيق و قمح 6
ملابس 4
منظمة الغذاء العالمي
بسكوت و كيك 1
خيام 6
دقيق و قمح 37
طرود غذائية 3
فحم جفت 2
منظفات 6
وزارة الاقتصاد الوطني
الإدارة العامة للتجارة والمعابر
"""


class CrossingTextTests(TestCase):
    def test_sample_day_is_read_and_zeros_wait_at_the_end(self):
        parsed = parse_crossing(SAMPLE)
        self.assertTrue(parsed.ready)
        self.assertEqual(parsed.movement_date.isoformat(), "2026-11-01")
        self.assertEqual(parsed.weekday, "الأحد")
        self.assertEqual(parsed.gates[0]["name"], "كرم أبو سالم")
        sheet = present(parsed)
        self.assertEqual(sheet["gates"][0]["lines"], [("التجاري", 144), ("المساعدات", 66), ("سولار المؤسسات", 11)])
        self.assertEqual(sheet["totals"], [("التجاري", 144), ("المساعدات", 66), ("المحروقات", 11)])
        self.assertEqual(sum(count for _name, count in sheet["loads"]), 144)
        self.assertEqual(sum(count for group in sheet["aid"] for _name, count in group["lines"]), 66)
        self.assertIn(("كيسوفيم، تجاري", 0), sheet["quiet"])
        self.assertIn(("زيكيم، مساعدات", 0), sheet["quiet"])
        self.assertIn(("بنزين تجاري", 0), sheet["quiet"])
        self.assertTrue(all(count == 0 for _name, count in sheet["quiet"]))
        self.assertIn("طرود غذائية", [line["item"] for line in parsed.aid_lines])

    def test_the_written_day_must_match_the_date(self):
        broken = SAMPLE.replace("الأحد", "الاثنين", 1)
        parsed = parse_crossing(broken)
        self.assertFalse(parsed.ready)
        self.assertIn("التاريخ 01/11/2026 يوافق الأحد", parsed.issues[0].message)
        self.assertIn("الاثنين", parsed.issues[0].message)
        by_name = parse_crossing(apply_correction(broken, parsed.issues[0].as_dict(), "الأحد"))
        self.assertTrue(by_name.ready)
        self.assertEqual(by_name.weekday, "الأحد")
        by_date = parse_crossing(apply_correction(broken, parsed.issues[0].as_dict(), "02/11/2026"))
        self.assertTrue(by_date.ready)
        self.assertEqual(by_date.movement_date.isoformat(), "2026-11-02")
        self.assertEqual(by_date.weekday, "الاثنين")

    def test_a_wrong_total_names_that_item_and_a_number_clears_it(self):
        broken = SAMPLE.replace("تجاري 144شاحنة", "تجاري 140شاحنة", 1)
        parsed = parse_crossing(broken)
        self.assertFalse(parsed.ready)
        self.assertIn("الإجمالي التجاري", parsed.issues[0].message)
        fixed = parse_crossing(apply_correction(broken, parsed.issues[0].as_dict(), "144"))
        self.assertTrue(fixed.ready)
        self.assertEqual(fixed.stated["commercial"], 144)


class CrossingPublishTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="commerce", password="password-long-12", role=User.Role.GOVERNOR,
            display_name="موظف التجارة", can_publish_crossings=True,
        )
        TelegramLink.objects.create(user=self.user, telegram_id="501")

    def test_publish_draws_the_sheet_and_a_second_copy_is_refused(self):
        _ask_crossing(501, self.user)
        consume_text(501, 501, SAMPLE)
        self.assertEqual(TelegramDraft.objects.get(chat_id="501").step, "office_cross_ready")
        handle_callback(501, 501, "crok")
        report = CrossingReport.objects.get(movement_date="2026-11-01")
        self.assertTrue(report.image.name.endswith(".png"))
        report.image.open("rb")
        self.assertTrue(report.image.read(8).startswith(b"\x89PNG"))
        self.assertEqual(report.gates.count(), 3)
        self.assertEqual(report.loads.count(), 16)
        sent = list(TelegramOutbox.objects.filter(chat_id="501").order_by("pk"))
        self.assertTrue(any(row.photo for row in sent))
        _ask_crossing(501, self.user)
        consume_text(501, 501, SAMPLE)
        self.assertEqual(CrossingReport.objects.filter(movement_date="2026-11-01").count(), 1)
        self.assertIn("تم إرسال تقرير هذا التاريخ سابقاً", TelegramOutbox.objects.filter(chat_id="501").latest("pk").text)

    def test_hiding_the_qr_redraws_the_published_sheet(self):
        from io import BytesIO

        from PIL import Image

        from apps.common.models import SystemSettings

        settings_row = SystemSettings.current()
        settings_row.crossing_qr_visible = True
        settings_row.save(update_fields=["crossing_qr_visible"])
        _ask_crossing(501, self.user)
        consume_text(501, 501, SAMPLE)
        handle_callback(501, 501, "crok")
        report = CrossingReport.objects.get(movement_date="2026-11-01")

        def dark_pixels(raw):
            crop = Image.open(BytesIO(raw)).crop((40, 32, 224, 216))
            return sum(1 for pixel in crop.getdata() if pixel[0] < 40)

        with report.image.open("rb") as stored:
            before = dark_pixels(stored.read())
        admin = User.objects.create_user(username="admin", password="admin-password-12", role="admin", display_name="مدير")
        self.client.force_login(admin)
        hidden = self.client.patch(
            "/api/system-settings/",
            data={"crossing_qr_visible": False},
            content_type="application/json",
        )
        self.assertEqual(hidden.status_code, 200)
        self.assertFalse(hidden.json()["crossing_qr_visible"])
        report.refresh_from_db()
        with report.image.open("rb") as stored:
            after = dark_pixels(stored.read())
        self.assertLess(after, before / 2)

    def test_public_day_page_is_the_sheet_without_login(self):
        _ask_crossing(501, self.user)
        consume_text(501, 501, SAMPLE)
        handle_callback(501, 501, "crok")
        page = self.client.get("/crossings/2026-11-01/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "sheet.png")
        self.assertNotContains(page, "تسجيل")
        image = self.client.get("/crossings/2026-11-01/sheet.png")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/crossings/2026-11-02/").status_code, 404)

    def test_history_shows_fifteen_then_the_older_sheet(self):
        from datetime import date, timedelta

        from django.core.files.base import ContentFile

        from apps.publications.crossing_text import WEEKDAYS
        from apps.telegram.webhook import handle_update

        def label(day):
            return f"{day.strftime('%d/%m/%Y')} {WEEKDAYS[day.weekday()]}"

        for offset in range(16):
            day = date(2026, 1, 1) + timedelta(days=offset)
            CrossingReport.objects.create(
                movement_date=day, weekday="الأحد", body="نص",
                image=ContentFile(b"png", name=f"{day.isoformat()}.png"),
                publisher=self.user, publisher_name="موظف التجارة",
            )
        handle_update({"message": {"chat": {"id": 501}, "from": {"id": 501}, "text": "سجل الحركات"}})
        first = TelegramOutbox.objects.filter(chat_id="501").latest("pk")
        labels = [button["text"] for row in first.markup["keyboard"] for button in row]
        self.assertEqual(len([item for item in labels if "/2026" in item]), 15)
        self.assertIn("التالي", labels)
        self.assertIn(label(date(2026, 1, 16)), labels)
        self.assertNotIn(label(date(2026, 1, 1)), labels)
        handle_update({"message": {"chat": {"id": 501}, "from": {"id": 501}, "text": "التالي"}})
        second = TelegramOutbox.objects.filter(chat_id="501").latest("pk")
        older = [button["text"] for row in second.markup["keyboard"] for button in row]
        oldest = label(date(2026, 1, 1))
        self.assertIn(oldest, older)
        self.assertIn("السابق", older)
        handle_update({"message": {"chat": {"id": 501}, "from": {"id": 501}, "text": oldest}})
        opened = TelegramOutbox.objects.filter(chat_id="501").latest("pk")
        self.assertIn("2026-01-01", opened.photo)

        handle_update({"message": {"chat": {"id": 501}, "from": {"id": 501}, "text": "سجل الأسعار"}})
        self.assertEqual(TelegramOutbox.objects.filter(chat_id="501").latest("pk").text, "غير مسموح.")

    def test_price_history_shows_fifteen_then_opens_one_list(self):
        from django.core.files.base import ContentFile

        from apps.accounts.models import StaffRole
        from apps.publications.models import PriceReport
        from apps.telegram.webhook import handle_update

        role = StaffRole.objects.get(name="موظف الأسعار")
        prices = User.objects.create_user(
            username="prices", password="password-long-12", role=role.kind, staff_role=role, display_name="الأسعار",
        )
        TelegramLink.objects.create(user=prices, telegram_id="502")
        for index in range(16):
            PriceReport.objects.create(
                image=ContentFile(b"jpg", name=f"list-{index}.jpg"), publisher=prices, publisher_name="الأسعار",
            )
        handle_update({"message": {"chat": {"id": 502}, "from": {"id": 502}, "text": "سجل الأسعار"}})
        first = TelegramOutbox.objects.filter(chat_id="502").latest("pk")
        labels = [button["text"] for row in first.markup["keyboard"] for button in row]
        self.assertEqual(len([label for label in labels if "(" in label]), 15)
        self.assertIn("التالي", labels)
        handle_update({"message": {"chat": {"id": 502}, "from": {"id": 502}, "text": "التالي"}})
        second = TelegramOutbox.objects.filter(chat_id="502").latest("pk")
        older = [button["text"] for row in second.markup["keyboard"] for button in row]
        chosen = next(label for label in older if "(" in label)
        handle_update({"message": {"chat": {"id": 502}, "from": {"id": 502}, "text": chosen}})
        self.assertIn("list-", TelegramOutbox.objects.filter(chat_id="502").latest("pk").photo)
