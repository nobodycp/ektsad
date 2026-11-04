from django.db import migrations


def align_field_roles(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    StaffRole.objects.filter(built_in=True, kind="inspector").update(
        can_view_field_missions=True,
        can_open_field_missions=True,
    )
    StaffRole.objects.filter(built_in=True, kind="governor").update(
        can_view_field_missions=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_staff_roster"),
    ]

    operations = [
        migrations.RunPython(align_field_roles, migrations.RunPython.noop),
    ]
