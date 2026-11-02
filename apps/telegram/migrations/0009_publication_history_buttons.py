from django.db import migrations


def add_history(apps, schema_editor):
    button = apps.get_model("telegram", "BotButton")
    if not button.objects.exists():
        return
    specs = (
        (6, 3, "سجل الأسعار", "ph:0", "can_publish_prices"),
        (6, 4, "سجل الحركات", "xh:0", "can_publish_crossings"),
    )
    for row, position, label, target, audience in specs:
        if button.objects.filter(target=target).exists():
            continue
        button.objects.create(
            row=row, position=position, label=label, target=target, audience=audience, enabled=True, style="",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("telegram", "0008_split_publish_buttons"),
    ]

    operations = [
        migrations.RunPython(add_history, migrations.RunPython.noop),
    ]
