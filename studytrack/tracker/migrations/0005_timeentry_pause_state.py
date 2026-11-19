import datetime

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0004_configure_site_domain"),
    ]

    operations = [
        migrations.AddField(
            model_name="timeentry",
            name="paused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="timeentry",
            name="paused_duration",
            field=models.DurationField(default=datetime.timedelta),
        ),
    ]
