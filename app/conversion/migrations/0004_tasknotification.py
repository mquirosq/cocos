from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0003_alter_fileupload_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('completed', 'Completed'), ('failed', 'Failed'), ('server_busy', 'Server Busy')], max_length=30)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('channels', models.JSONField(blank=True, default=list)),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='conversion.conversiontask')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'converter_tasknotification',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='tasknotification',
            index=models.Index(fields=['user', 'is_read', '-created_at'], name='converter_ta_user_id_c671f8_idx'),
        ),
        migrations.AddIndex(
            model_name='tasknotification',
            index=models.Index(fields=['user', '-created_at'], name='converter_ta_user_id_fa2b97_idx'),
        ),
    ]
