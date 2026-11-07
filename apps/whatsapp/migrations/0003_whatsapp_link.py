from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("whatsapp", "0002_lengthen_message_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(max_length=32, unique=True)),
                ("linked_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=models.CASCADE, related_name="whatsapp_link", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
