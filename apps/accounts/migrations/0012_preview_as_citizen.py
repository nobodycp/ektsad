from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_preview_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preview_as_citizen",
            field=models.BooleanField(default=False),
        ),
    ]
