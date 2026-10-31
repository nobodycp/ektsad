from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="whatsappinbound",
            name="message_id",
            field=models.CharField(max_length=512, unique=True),
        ),
    ]
