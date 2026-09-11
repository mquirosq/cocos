import os

import django.db.models.deletion
from django.db import migrations, models


def _infer_file_type(filename):
    name = (filename or '').lower()
    if name.endswith('.gz'):
        name = name[:-3]

    ext = os.path.splitext(name)[1]
    if ext in {'.fa', '.fasta', '.fna', '.ffn', '.faa', '.frn'}:
        return 'fasta'
    if ext in {'.fq', '.fastq'}:
        return 'fastq'
    if ext == '.json':
        return 'json'
    if ext == '.csv':
        return 'csv'
    return 'fastq'


def populate_file_types(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('SELECT id, file FROM model_file')
        rows = cursor.fetchall()

        for file_id, file_name in rows:
            cursor.execute(
                'UPDATE model_file SET file_type = %s WHERE id = %s AND file_type IS NULL',
                [_infer_file_type(file_name), file_id],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0006_conversiontask_output_path'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE model_fileupload RENAME TO model_file;',
                    reverse_sql='ALTER TABLE model_file RENAME TO model_fileupload;',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE model_file RENAME COLUMN uploaded_at TO created_at;',
                    reverse_sql='ALTER TABLE model_file RENAME COLUMN created_at TO uploaded_at;',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE model_file ADD COLUMN file_type varchar(50) NULL;',
                    reverse_sql='ALTER TABLE model_file DROP COLUMN file_type;',
                ),
                migrations.RunPython(populate_file_types, migrations.RunPython.noop),
                migrations.RunSQL(
                    sql='ALTER TABLE model_file ALTER COLUMN file_type SET NOT NULL;',
                    reverse_sql='ALTER TABLE model_file ALTER COLUMN file_type DROP NOT NULL;',
                ),
            ],
            state_operations=[
                migrations.RenameModel(
                    old_name='FileUpload',
                    new_name='File',
                ),
                migrations.AlterModelTable(
                    name='file',
                    table='model_file',
                ),
                migrations.RenameField(
                    model_name='file',
                    old_name='uploaded_at',
                    new_name='created_at',
                ),
                migrations.AddField(
                    model_name='file',
                    name='file_type',
                    field=models.CharField(
                        choices=[
                            ('fastq', 'FASTQ'),
                            ('fasta', 'FASTA'),
                            ('json', 'JSON'),
                            ('csv', 'CSV'),
                        ],
                        max_length=50,
                    ),
                ),
                migrations.AlterField(
                    model_name='filegene',
                    name='file_upload',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='conversion.file'),
                ),
            ],
        ),
    ]