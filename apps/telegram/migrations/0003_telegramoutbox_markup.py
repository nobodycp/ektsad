from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("telegram", "0002_telegramoutbox_photo")]

    operations = [
        migrations.AddField(
            model_name="telegramoutbox",
            name="markup",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
