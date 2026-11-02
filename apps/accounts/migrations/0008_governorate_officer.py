from django.db import migrations


def add_officer(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    if StaffRole.objects.filter(name="إداري المحافظة").exists():
        return
    StaffRole.objects.create(
        name="إداري المحافظة",
        kind="custom",
        built_in=False,
        can_login_web=True,
        can_view_reports=True,
        can_view_field_missions=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_governors_director"),
    ]

    operations = [
        migrations.RunPython(add_officer, migrations.RunPython.noop),
    ]
