from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_can_login_web"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_open_field_missions",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="can_view_field_missions",
            field=models.BooleanField(default=False),
        ),
    ]
