from django.db import migrations


def rename_entry(apps, schema_editor):
    button = apps.get_model("telegram", "BotButton")
    button.objects.filter(target="crb", label="نشر المعابر").update(label="إدخال تقرير")


class Migration(migrations.Migration):

    dependencies = [
        ("telegram", "0006_botbutton_style"),
    ]

    operations = [
        migrations.RunPython(rename_entry, migrations.RunPython.noop),
    ]
