from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("telegram", "0003_telegramoutbox_markup")]

    operations = [
        migrations.AddField(
            model_name="telegramlink",
            name="telegram_username",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="telegramlink",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
