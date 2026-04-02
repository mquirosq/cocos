from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def ensure_user_notification_settings_table(apps, schema_editor):
    from notifications.models import UserNotificationSettings

    existing_tables = set(schema_editor.connection.introspection.table_names())
    if UserNotificationSettings._meta.db_table in existing_tables:
        return

    schema_editor.create_model(UserNotificationSettings)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(ensure_user_notification_settings_table, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='UserNotificationSettings',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('email_notifications_enabled', models.BooleanField(default=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        (
                            'user',
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='notification_settings',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        'db_table': 'home_usernotificationsettings',
                    },
                ),
            ],
        ),
    ]
