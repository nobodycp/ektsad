import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0003_field_mission_flags"),
        ("geography", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FieldMission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[
                    ("ضبط", "ضبط"),
                    ("تحفظ", "تحفظ"),
                    ("إثبات حالة", "إثبات حالة"),
                    ("مصادرة", "مصادرة"),
                    ("إتلاف", "إتلاف"),
                    ("عينات فحص", "عينات فحص"),
                    ("أخرى", "أخرى"),
                ], max_length=32)),
                ("details", models.TextField()),
                ("place_name", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=32)),
                ("image", models.ImageField(blank=True, null=True, upload_to="field-missions/")),
                ("created_by_name", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_field_missions", to="accounts.user")),
                ("governorate", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="geography.governorate")),
                ("region", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="geography.region")),
            ],
        ),
        migrations.CreateModel(
            name="FieldMissionAssignee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=255)),
                ("mission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignees", to="field_missions.fieldmission")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="field_mission_duties", to="accounts.user")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("mission", "user"), name="unique_field_mission_assignee")
                ],
            },
        ),
    ]
