import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_notification_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())

    old_settings = 'home_usernotificationsettings'
    new_settings = 'notifications_usernotificationsettings'
    old_task = 'converter_tasknotification'
    new_task = 'notifications_tasknotification'

    with schema_editor.connection.cursor() as cursor:
        if old_settings in existing_tables and new_settings not in existing_tables:
            cursor.execute(f'ALTER TABLE "{old_settings}" RENAME TO "{new_settings}"')
            existing_tables.remove(old_settings)
            existing_tables.add(new_settings)

        if old_task in existing_tables and new_task not in existing_tables:
            cursor.execute(f'ALTER TABLE "{old_task}" RENAME TO "{new_task}"')
            existing_tables.remove(old_task)
            existing_tables.add(new_task)


def reverse_move_notification_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())

    old_settings = 'home_usernotificationsettings'
    new_settings = 'notifications_usernotificationsettings'
    old_task = 'converter_tasknotification'
    new_task = 'notifications_tasknotification'

    with schema_editor.connection.cursor() as cursor:
        if new_settings in existing_tables and old_settings not in existing_tables:
            cursor.execute(f'ALTER TABLE "{new_settings}" RENAME TO "{old_settings}"')
            existing_tables.remove(new_settings)
            existing_tables.add(old_settings)

        if new_task in existing_tables and old_task not in existing_tables:
            cursor.execute(f'ALTER TABLE "{new_task}" RENAME TO "{old_task}"')
            existing_tables.remove(new_task)
            existing_tables.add(old_task)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_ensure_tasknotification_table'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(move_notification_tables, reverse_move_notification_tables),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='TaskNotification',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('event_type', models.CharField(choices=[('started', 'Started'), ('completed', 'Completed'), ('failed', 'Failed'), ('server_busy', 'Server Busy')], max_length=30)),
                        ('message', models.TextField()),
                        ('is_read', models.BooleanField(default=False)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('channels', models.JSONField(blank=True, default=list)),
                        ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='conversion.conversiontask')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_notifications', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'notifications_tasknotification',
                        'ordering': ['-created_at'],
                    },
                ),
                migrations.AlterModelTable(
                    name='usernotificationsettings',
                    table='notifications_usernotificationsettings',
                ),
            ],
        ),
    ]
