import django.db.models.deletion
from django.core.management.color import no_style
from django.db import migrations, models
from django.db.migrations.operations.base import Operation


def run_deferred_constraints(schema_editor):
    """
    Check deferred FK constraints now. Postgres refuses to ALTER a table with pending
    trigger events, which data changes leave behind inside the migration transaction.
    """
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


class AlterModelBases(Operation):
    """State-only operation to change a model's bases (the autodetector does not track them)."""
    reduces_to_sql = False
    reversible = True

    def __init__(self, name, bases, old_bases=('django.db.models.Model',)):
        self.name = name
        self.bases = tuple(bases)
        self.old_bases = tuple(old_bases)

    def deconstruct(self):
        return (self.__class__.__qualname__, [self.name, self.bases, self.old_bases], {})

    def _set_bases(self, app_label, state, bases):
        model_key = (app_label, self.name.lower())
        state.models[model_key].bases = bases
        state.reload_model(*model_key, delay=False)

    def state_forwards(self, app_label, state):
        self._set_bases(app_label, state, self.bases)

    def state_backwards(self, app_label, state):
        self._set_bases(app_label, state, self.old_bases)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def describe(self):
        return f"Change bases of {self.name} to {self.bases}"


def copy_to_parent_tasks(apps, schema_editor):
    """Create a parent Task for every ConversionTask, keeping the same id."""
    Task = apps.get_model('core', 'Task')
    ConversionTask = apps.get_model('conversion', 'ConversionTask')
    db = schema_editor.connection.alias

    for conversion in ConversionTask.objects.using(db).order_by('id'):
        Task.objects.using(db).create(id=conversion.id, status=conversion.status)
        # auto_now/auto_now_add overwrite the original timestamps on create
        Task.objects.using(db).filter(id=conversion.id).update(
            created_at=conversion.created_at,
            updated_at=conversion.updated_at,
        )

    # Explicit ids were inserted, so move the Task id sequence past them
    with schema_editor.connection.cursor() as cursor:
        for sql in schema_editor.connection.ops.sequence_reset_sql(no_style(), [Task]):
            cursor.execute(sql)
    run_deferred_constraints(schema_editor)


def copy_from_parent_tasks(apps, schema_editor):
    Task = apps.get_model('core', 'Task')
    ConversionTask = apps.get_model('conversion', 'ConversionTask')
    db = schema_editor.connection.alias

    tasks = Task.objects.using(db).filter(id__in=ConversionTask.objects.using(db).values('id'))
    for task in tasks:
        ConversionTask.objects.using(db).filter(id=task.id).update(
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    tasks.delete()
    run_deferred_constraints(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('conversion', '0001_initial'),
        ('core', '0002_task'),
    ]

    operations = [
        migrations.RunPython(copy_to_parent_tasks, copy_from_parent_tasks),
        migrations.RemoveField(model_name='conversiontask', name='status'),
        migrations.RemoveField(model_name='conversiontask', name='created_at'),
        migrations.RemoveField(model_name='conversiontask', name='updated_at'),
        # Turn the existing id column into the parent link to core.Task
        migrations.AlterField(
            model_name='conversiontask',
            name='id',
            field=models.BigIntegerField(db_column='id', primary_key=True, serialize=False),
        ),
        migrations.RenameField(model_name='conversiontask', old_name='id', new_name='task_ptr'),
        migrations.AlterField(
            model_name='conversiontask',
            name='task_ptr',
            field=models.OneToOneField(db_column='id', on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.task'),
        ),
        AlterModelBases('conversiontask', ('core.task',)),
    ]
