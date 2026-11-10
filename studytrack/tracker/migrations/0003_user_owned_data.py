from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def refuse_legacy_data_loss(apps, schema_editor):
    database = schema_editor.connection.alias
    TimeEntry = apps.get_model("tracker", "TimeEntry")
    Subject = apps.get_model("tracker", "Subject")
    has_entries = TimeEntry.objects.using(database).exists()
    has_subjects = Subject.objects.using(database).exists()
    if has_entries or has_subjects:
        raise RuntimeError(
            "The account-ownership migration found existing study data and stopped "
            "to prevent data loss. Back up and assign the legacy data before retrying."
        )


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
        migrations.RunPython(refuse_legacy_data_loss),
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
