from django.db import migrations, models


def color_public_buttons(apps, schema_editor):
    BotButton = apps.get_model("telegram", "BotButton")
    layout = {
        "تقديم شكوى": (1, 1, "danger"),
        "القائمة الاسترشادية": (2, 1, "primary"),
        "حركة المعابر": (3, 1, "success"),
        "الشكاوى": (4, 1, ""),
        "المهمات": (5, 1, ""),
        "إنشاء مهمة": (5, 2, ""),
        "نشر الأسعار": (6, 1, ""),
        "نشر المعابر": (6, 2, ""),
        "التقارير": (7, 1, ""),
        "المستخدمون": (8, 1, ""),
        "المحافظات": (9, 1, ""),
        "المناطق": (9, 2, ""),
        "إعدادات النظام": (10, 1, ""),
    }
    for label, (row, position, style) in layout.items():
        BotButton.objects.filter(label=label).update(row=row, position=position, style=style)


class Migration(migrations.Migration):

    dependencies = [("telegram", "0005_botbutton")]

    operations = [
        migrations.AddField(
            model_name="botbutton",
            name="style",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.RunPython(color_public_buttons, migrations.RunPython.noop),
    ]
