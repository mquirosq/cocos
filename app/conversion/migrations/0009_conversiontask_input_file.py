import os
import hashlib

import django.db.models.deletion
from django.db import migrations, models


FASTA_EXTENSIONS = {'.fa', '.fasta', '.fna', '.ffn', '.faa', '.frn'}
FASTQ_EXTENSIONS = {'.fastq', '.fq'}
JSON_EXTENSIONS = {'.json'}


def _derive_file_type(task_type, source_name):
    extension = os.path.splitext((source_name or '').split(',')[0].strip().lower())[1]

    if extension in FASTQ_EXTENSIONS or task_type in {'assembly_ont', 'assembly_illumina', 'assembly_ont_annotated', 'assembly_illumina_annotated'}:
        return 'fastq'
    if extension in JSON_EXTENSIONS or task_type == 'from_json':
        return 'json'
    if extension in FASTA_EXTENSIONS or task_type == 'annotation':
        return 'fasta'
    return 'fasta'


def _safe_file_name(task, source_name):
    base_name = os.path.basename(source_name)
    if len(base_name) <= 100:
        return base_name

    stem, extension = os.path.splitext(base_name)
    digest = hashlib.sha1(source_name.encode('utf-8')).hexdigest()[:12]
    prefix = f'legacy_{task.id}_{digest}_'
    max_stem_length = max(1, 100 - len(prefix) - len(extension))
    return f"{prefix}{stem[:max_stem_length]}{extension}"


def backfill_input_file(apps, schema_editor):
    ConversionTask = apps.get_model('conversion', 'ConversionTask')
    File = apps.get_model('conversion', 'File')

    for task in ConversionTask.objects.select_related('user').order_by('id'):
        if task.input_file_id:
            continue

        legacy_value = getattr(task, 'input_path', None)
        if not legacy_value:
            continue

        source_name = legacy_value.split(',')[0].strip()
        if not source_name:
            continue

        file_type = _derive_file_type(task.task_type, source_name)
        safe_name = _safe_file_name(task, source_name)
        upload = File.objects.filter(user_id=task.user_id, file=safe_name).first()
        if not upload:
            upload = File.objects.filter(user_id=task.user_id, file__endswith=os.path.basename(source_name)).order_by('-created_at', '-id').first()
        if not upload:
            upload = File.objects.create(user_id=task.user_id, file=safe_name, file_type=file_type)

        task.input_file = upload
        task.save(update_fields=['input_file'])


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0008_alter_conversiontask_task_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversiontask',
            name='input_file',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='input_conversion_tasks', to='conversion.file'),
        ),
        migrations.RunPython(
            code=backfill_input_file,
            reverse_code=migrations.RunPython.noop,
        ),
    ]