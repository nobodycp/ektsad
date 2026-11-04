from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="linked_complaint_button",
            field=models.BooleanField(default=False),
        ),
    ]
