import django.db.models.deletion
from django.db import migrations, models


def copy_process_from_task(apps, schema_editor):
    """Rollback only: restore the subclass 'process' from Task.process_new."""
    Task = apps.get_model('core', 'Task')
    PredictionTask = apps.get_model('prediction', 'PredictionTask')
    db = schema_editor.connection.alias

    tasks = Task.objects.using(db).filter(pk__in=PredictionTask.objects.using(db).values('pk'))
    for task_id, process_id in tasks.values_list('pk', 'process_new_id'):
        PredictionTask.objects.using(db).filter(pk=task_id).update(process_id=process_id)

    # Postgres refuses the following ALTER TABLE while deferred FK checks are pending
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


class Migration(migrations.Migration):
    """Step 2/3: drop the subclass 'process' field, now stored on core.Task."""

    dependencies = [
        ('prediction', '0003_predictiontask_task_inheritance'),
        ('core', '0003_task_process_new'),
    ]

    operations = [
        # Nullable first so the field can be re-added on rollback before data is copied back
        migrations.AlterField(
            model_name='predictiontask',
            name='process',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='prediction_tasks', to='core.processgroup'),
        ),
        migrations.RunPython(migrations.RunPython.noop, copy_process_from_task),
        migrations.RemoveField(model_name='predictiontask', name='process'),
    ]
