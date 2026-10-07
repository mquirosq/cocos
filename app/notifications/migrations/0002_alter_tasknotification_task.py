import django.db.models.deletion
from django.db import migrations, models


def run_deferred_constraints(schema_editor):
    """
    Check deferred FK constraints now. Postgres refuses to ALTER a table with pending
    trigger events, which data changes leave behind inside the migration transaction.
    """
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


def unlink_non_conversion_tasks(apps, schema_editor):
    """Before going back to a FK to ConversionTask, drop links to other task types."""
    TaskNotification = apps.get_model('notifications', 'TaskNotification')
    ConversionTask = apps.get_model('conversion', 'ConversionTask')
    db = schema_editor.connection.alias

    TaskNotification.objects.using(db).exclude(task__isnull=True).exclude(
        task_id__in=ConversionTask.objects.using(db).values('pk'),
    ).update(task=None)
    run_deferred_constraints(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
        ('core', '0002_task'),
        ('conversion', '0002_conversiontask_task_inheritance'),
        ('prediction', '0003_predictiontask_task_inheritance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tasknotification',
            name='task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='core.task'),
        ),
        migrations.RunPython(migrations.RunPython.noop, unlink_non_conversion_tasks),
    ]
