from django.db import migrations, models


def seed_buttons(apps, schema_editor):
    BotButton = apps.get_model("telegram", "BotButton")
    if BotButton.objects.exists():
        return
    defaults = (
        (1, 1, "تقديم شكوى", "nw", "everyone"),
        (2, 1, "حركة المعابر", "cr", "everyone"),
        (2, 2, "القائمة الاسترشادية", "pr", "everyone"),
        (3, 1, "الشكاوى", "ls:a:0", "linked"),
        (4, 1, "المهمات", "ms:0", "can_view_field_missions"),
        (4, 2, "إنشاء مهمة", "mc", "can_open_field_missions"),
        (5, 1, "نشر الأسعار", "prb", "can_publish"),
        (5, 2, "نشر المعابر", "crb", "can_publish"),
        (6, 1, "التقارير", "rp", "reports"),
        (7, 1, "المستخدمون", "us:0", "can_manage_users"),
        (8, 1, "المحافظات", "gv:0", "can_manage_geography"),
        (8, 2, "المناطق", "rg:0", "can_manage_geography"),
        (9, 1, "إعدادات النظام", "st", "can_manage_settings"),
    )
    BotButton.objects.bulk_create([
        BotButton(row=row, position=position, label=label, target=target, audience=audience)
        for row, position, label, target, audience in defaults
    ])


class Migration(migrations.Migration):
    dependencies = [("telegram", "0004_telegramlink_presence")]

    operations = [
        migrations.CreateModel(
            name="BotButton",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=64)),
                ("target", models.CharField(max_length=32)),
                ("audience", models.CharField(max_length=32)),
                ("row", models.PositiveSmallIntegerField(default=1)),
                ("position", models.PositiveSmallIntegerField(default=1)),
                ("enabled", models.BooleanField(default=True)),
            ],
            options={"ordering": ["row", "position", "pk"]},
        ),
        migrations.RunPython(seed_buttons, migrations.RunPython.noop),
    ]
