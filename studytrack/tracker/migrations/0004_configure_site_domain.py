from django.conf import settings
from django.db import migrations


def configure_site_domain(apps, schema_editor):
    database = schema_editor.connection.alias
    Site = apps.get_model("sites", "Site")
    Site.objects.using(database).update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": settings.SITE_DOMAIN, "name": "StudyTrack"},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0002_alter_domain_unique"),
        ("tracker", "0003_user_owned_data"),
    ]

    operations = [
        migrations.RunPython(configure_site_domain, migrations.RunPython.noop),
    ]
