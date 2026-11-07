from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def clear_pre_account_data(apps, schema_editor):
    """Remove shared pre-auth data so it cannot be claimed by the first account."""
    database = schema_editor.connection.alias
    TimeEntry = apps.get_model("tracker", "TimeEntry")
    Subject = apps.get_model("tracker", "Subject")
    TimeEntry.objects.using(database).all().delete()
    Subject.objects.using(database).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0002_alter_timeentry_activity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subjects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="timeentry",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="time_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(clear_pre_account_data),
        migrations.AlterField(
            model_name="subject",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subjects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="timeentry",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="time_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="subject",
            name="name",
            field=models.CharField(max_length=120),
        ),
        migrations.AddConstraint(
            model_name="subject",
            constraint=models.UniqueConstraint(fields=("user", "name"), name="unique_subject_name_per_user"),
        ),
    ]
