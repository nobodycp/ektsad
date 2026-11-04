from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0002_linked_complaint_button"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="linked_bulletin_buttons",
            field=models.BooleanField(default=False),
        ),
    ]
