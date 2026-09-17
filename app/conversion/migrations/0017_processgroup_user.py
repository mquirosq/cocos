from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_process_group_users(apps, schema_editor):
    ProcessGroup = apps.get_model('conversion', 'ProcessGroup')
    ConversionTask = apps.get_model('conversion', 'ConversionTask')

    for process in ProcessGroup.objects.order_by('id'):
        task = ConversionTask.objects.filter(process_id=process.id).order_by('id').first()
        if task is not None:
            process.user_id = task.user_id
            process.save(update_fields=['user'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('conversion', '0016_remove_conversiontask_process_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='processgroup',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='process_groups',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_process_group_users, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='processgroup',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='process_groups',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]