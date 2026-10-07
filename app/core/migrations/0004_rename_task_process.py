import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 3/3: give Task.process its final name and make it required."""

    dependencies = [
        ('core', '0003_task_process_new'),
        ('conversion', '0003_remove_conversiontask_process'),
        ('prediction', '0004_remove_predictiontask_process'),
    ]

    operations = [
        migrations.RenameField(model_name='task', old_name='process_new', new_name='process'),
        migrations.AlterField(
            model_name='task',
            name='process',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tasks', to='core.processgroup'),
        ),
    ]
