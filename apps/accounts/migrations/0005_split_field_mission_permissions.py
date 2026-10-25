from django.db import migrations, models


def copy_field_mission_flag(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    for role in StaffRole.objects.all():
        role.can_view_field_missions = role.can_field_missions
        role.can_open_field_missions = role.can_field_missions
        role.save(update_fields=["can_view_field_missions", "can_open_field_missions"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_staff_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffrole",
            name="can_open_field_missions",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="staffrole",
            name="can_view_field_missions",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copy_field_mission_flag, migrations.RunPython.noop),
    ]
