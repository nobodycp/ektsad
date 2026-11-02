from django.db import migrations, models


def split_publish(apps, schema_editor):
    StaffRole = apps.get_model("accounts", "StaffRole")
    for role in StaffRole.objects.all():
        role.can_publish_prices = role.can_publish
        role.can_publish_crossings = role.can_publish
        role.save(update_fields=["can_publish_prices", "can_publish_crossings"])
    specs = (
        ("موظف المعابر", False, True),
        ("موظف الأسعار", True, False),
    )
    for name, prices, crossings in specs:
        if StaffRole.objects.filter(name=name).exists():
            continue
        StaffRole.objects.create(
            name=name,
            kind="custom",
            built_in=False,
            can_login_web=True,
            can_publish=True,
            can_publish_prices=prices,
            can_publish_crossings=crossings,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_split_field_mission_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffrole",
            name="can_publish_crossings",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="staffrole",
            name="can_publish_prices",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(split_publish, migrations.RunPython.noop),
    ]
