from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("publications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="crossingreport",
            name="movement_date",
            field=models.DateField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="crossingreport",
            name="weekday",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.CreateModel(
            name="CrossingGate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("commercial", models.PositiveIntegerField(default=0)),
                ("aid", models.PositiveIntegerField(default=0)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gates", to="publications.crossingreport")),
            ],
        ),
        migrations.CreateModel(
            name="CrossingFuel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gate", models.CharField(max_length=80)),
                ("party", models.CharField(max_length=20)),
                ("kind", models.CharField(max_length=20)),
                ("count", models.PositiveIntegerField(default=0)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fuels", to="publications.crossingreport")),
            ],
        ),
        migrations.CreateModel(
            name="CrossingLoad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("count", models.PositiveIntegerField(default=0)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="loads", to="publications.crossingreport")),
            ],
        ),
        migrations.CreateModel(
            name="CrossingAidLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization", models.CharField(max_length=120)),
                ("item", models.CharField(max_length=80)),
                ("count", models.PositiveIntegerField(default=0)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="aid_lines", to="publications.crossingreport")),
            ],
        ),
    ]
