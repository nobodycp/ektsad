import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_can_login_web"),
        ("complaints", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComplaintSeen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seen_at", models.DateTimeField(auto_now_add=True)),
                (
                    "complaint",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seen_by",
                        to="complaints.complaint",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seen_complaints",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("user", "complaint"), name="unique_complaint_seen")
                ]
            },
        ),
    ]
