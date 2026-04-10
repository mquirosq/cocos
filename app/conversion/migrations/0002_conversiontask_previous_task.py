from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversiontask',
            name='previous_task',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='derived_tasks', to='conversion.conversiontask'),
        ),
    ]
