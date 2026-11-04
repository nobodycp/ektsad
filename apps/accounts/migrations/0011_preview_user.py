import sys

from django.db import migrations, models


PASSWORD_HASH = "pbkdf2_sha256$1000000$305azwEBwO0nUH2DH6yciz$IGO9GGj6BBrIE0TanCeQPs4FxaeakQaC66qYNht8qcA="


def create_preview_user(apps, schema_editor):
    if "test" in sys.argv:
        return
    User = apps.get_model("accounts", "User")
    StaffRole = apps.get_model("accounts", "StaffRole")
    role = StaffRole.objects.filter(name="مدير المحافظات").first()
    existing = User.objects.filter(username="preview").first()
    if existing is not None:
        existing.display_name = "يوزر استعراضي"
        existing.is_preview = True
        existing.role = "custom"
        existing.staff_role = role
        existing.is_active = True
        existing.save()
        return
    User.objects.create(
        username="preview",
        display_name="يوزر استعراضي",
        password=PASSWORD_HASH,
        role="custom",
        staff_role=role,
        is_preview=True,
        is_active=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_align_field_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_preview",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(create_preview_user, migrations.RunPython.noop),
    ]
