from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_admin_to_orphan_rows(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    UserModel = apps.get_model(app_label, model_name)
    ConversionTask = apps.get_model('conversion', 'ConversionTask')
    FileUpload = apps.get_model('conversion', 'FileUpload')

    admin_user = UserModel.objects.filter(username='admin').first()
    if admin_user is None:
        raise RuntimeError("Admin user with username 'admin' was not found. Create it before running this migration.")

    ConversionTask.objects.filter(user__isnull=True).update(user=admin_user)
    FileUpload.objects.filter(user__isnull=True).update(user=admin_user)


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0002_conversiontask_user_fileupload_user_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(assign_admin_to_orphan_rows, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='conversiontask',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='conversion_tasks', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='fileupload',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='uploaded_files', to=settings.AUTH_USER_MODEL),
        ),
    ]
