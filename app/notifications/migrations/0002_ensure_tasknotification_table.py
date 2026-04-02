from django.conf import settings
from django.db import migrations


def ensure_tasknotification_table(apps, schema_editor):
    from notifications.models import TaskNotification

    existing_tables = set(schema_editor.connection.introspection.table_names())
    if TaskNotification._meta.db_table in existing_tables:
        return

    schema_editor.create_model(TaskNotification)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
        ('conversion', '0004_tasknotification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(ensure_tasknotification_table, migrations.RunPython.noop),
    ]
