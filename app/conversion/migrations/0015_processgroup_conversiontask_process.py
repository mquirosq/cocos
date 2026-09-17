from django.db import migrations, models
import django.db.models.deletion


def backfill_process_groups(apps, schema_editor):
    ProcessGroup = apps.get_model('conversion', 'ProcessGroup')
    ConversionTask = apps.get_model('conversion', 'ConversionTask')

    groups = {}
    for task in ConversionTask.objects.order_by('id'):
        name = task.process_name or f'Process {task.id}'
        key = (task.user_id, name)
        process = groups.get(key)
        if process is None:
            process = ProcessGroup.objects.create(name=name)
            groups[key] = process
        task.process_id = process.id
        task.save(update_fields=['process'])


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0014_remove_conversiontask_output_file_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name='conversiontask',
            name='process',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='conversion_tasks',
                to='conversion.processgroup',
            ),
        ),
        migrations.RunPython(backfill_process_groups, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='conversiontask',
            name='process',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='conversion_tasks',
                to='conversion.processgroup',
            ),
        ),
    ]