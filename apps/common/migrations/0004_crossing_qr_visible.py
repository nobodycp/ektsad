from django.db import migrations, models


def hide_previous_qr(apps, schema_editor):
    from apps.publications.crossing_sheet import refresh_crossing_sheets

    refresh_crossing_sheets()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0003_linked_bulletin_buttons"),
        ("publications", "0002_crossing_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="crossing_qr_visible",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(hide_previous_qr, migrations.RunPython.noop),
    ]
