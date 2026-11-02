from django.db import migrations


def add_director(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    if StaffRole.objects.filter(name="مدير المحافظات").exists():
        return
    StaffRole.objects.create(
        name="مدير المحافظات",
        kind="custom",
        built_in=False,
        can_login_web=True,
        can_view_all_complaints=True,
        can_view_reports=True,
        can_view_field_missions=True,
        can_open_field_missions=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_publisher_roles"),
    ]

    operations = [
        migrations.RunPython(add_director, migrations.RunPython.noop),
    ]
