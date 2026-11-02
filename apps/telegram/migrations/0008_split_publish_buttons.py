from django.db import migrations


def split_buttons(apps, schema_editor):
    button = apps.get_model("telegram", "BotButton")
    button.objects.filter(target="prb").update(audience="can_publish_prices")
    button.objects.filter(target="crb").update(audience="can_publish_crossings")


class Migration(migrations.Migration):

    dependencies = [
        ("telegram", "0007_crossing_entry_label"),
    ]

    operations = [
        migrations.RunPython(split_buttons, migrations.RunPython.noop),
    ]
