from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0002_complaintseen"),
    ]

    operations = [
        migrations.AddField(
            model_name="complaint",
            name="return_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="complaint",
            name="returned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
