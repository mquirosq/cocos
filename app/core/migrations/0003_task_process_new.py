import django.db.models.deletion
from django.db import migrations, models


def copy_process_from_children(apps, schema_editor):
    Task = apps.get_model('core', 'Task')
    db = schema_editor.connection.alias

    for app_label, model_name in (('conversion', 'ConversionTask'), ('prediction', 'PredictionTask')):
        Child = apps.get_model(app_label, model_name)
        for task_id, process_id in Child.objects.using(db).values_list('pk', 'process_id'):
            Task.objects.using(db).filter(pk=task_id).update(process_new_id=process_id)


class Migration(migrations.Migration):
    """
    Step 1/3 of moving 'process' from the task subclasses to Task. A temporary name is
    needed because a parent and its children cannot both declare a 'process' field.
    """

    dependencies = [
        ('core', '0002_task'),
        ('conversion', '0002_conversiontask_task_inheritance'),
        ('prediction', '0003_predictiontask_task_inheritance'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='process_new',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='tasks', to='core.processgroup'),
        ),
        # Rolling back, each subclass migration copies process back before it becomes required
        migrations.RunPython(copy_process_from_children, migrations.RunPython.noop),
    ]
