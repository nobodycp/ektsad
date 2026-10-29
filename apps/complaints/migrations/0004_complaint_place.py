from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("complaints", "0003_complaint_return")]

    operations = [
        migrations.AddField(
            model_name="complaint",
            name="kind",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="complaint",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="complaint",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]
