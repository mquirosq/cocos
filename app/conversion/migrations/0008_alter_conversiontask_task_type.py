from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0007_rename_fileupload_to_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversiontask',
            name='task_type',
            field=models.CharField(
                choices=[
                    ('annotation', 'Annotation'),
                    ('from_json', 'From JSON'),
                    ('assembly_ont', 'ONT Assembly'),
                    ('assembly_illumina', 'Illumina Assembly'),
                    ('assembly_ont_annotated', 'ONT Assembly with Annotation'),
                    ('assembly_illumina_annotated', 'Illumina Assembly with Annotation'),
                    ('prediction', 'Prediction'),
                ],
                max_length=50,
            ),
        ),
    ]