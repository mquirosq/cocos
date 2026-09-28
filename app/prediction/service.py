from django.db import models

from .models import PredictionTask
from conversion.models import ConversionTask
from core.models import File
from conversion.services.presentation import format_process_label
from conversion.task_types import ANNOTATED_TYPES

from .registry import get_model_supported_antibiotics
from .tasks import predict


def get_prediction_input_options(user):
    tasks_json = ConversionTask.objects.filter(
        models.Q(task_type=ConversionTask.ConversionTaskType.FROM_JSON) |
        models.Q(task_type__in=ANNOTATED_TYPES),
        process__user=user,
    ).order_by('-created_at')
    options = []

    for task in tasks_json:

        json_file = None
        if task.task_type == ConversionTask.ConversionTaskType.FROM_JSON:
            json_file = task.input_files.filter(file_type=File.FileType.JSON).first()
        else: 
            json_file = task.output_files.filter(file_type=File.FileType.JSON).first()

        if not json_file:
            continue

        options.append({
            'id': str(json_file.id),
            'label': format_process_label(task),
        })

    return options

def get_valid_prediction_antibiotics(model_names, antibiotics):
    return [antibiotic for antibiotic in antibiotics if 
            any(antibiotic in get_model_supported_antibiotics(model_name) for model_name in model_names)]

def _get_source_task_for_prediction(file):
    source_task = file.output_conversion_tasks.first()
    if not source_task:
        source_task = file.input_conversion_tasks.first()
    return source_task

def get_prediction_file(user, file_id):
    if not file_id:
        raise ValueError('Select a dataset.')
    
    try:
        return File.objects.get(pk=int(file_id), user=user, file_type=File.FileType.JSON)
    except (ValueError, File.DoesNotExist):
        raise ValueError('Selected file not found.')

def start_prediction(user, model_names, antibiotics, file_id):
    if not model_names:
        raise ValueError('Select at least one model.')

    if not antibiotics:
        raise ValueError('Select at least one antibiotic.')

    file = get_prediction_file(user, file_id)

    valid_antibiotics = get_valid_prediction_antibiotics(model_names, antibiotics)

    if not valid_antibiotics:
        raise ValueError('No valid antibiotic/model combinations found.')
    
    source_task = _get_source_task_for_prediction(file)

    task = PredictionTask.objects.create(
        process=source_task.process,
        selected_models=model_names,
        selected_antibiotics=valid_antibiotics,
        )

    # TODO: Make really async with Celery, for now sync
    return predict(
        task_id=task.id,
        file_id=file.id if file else None,
    )

def prepare_prediction_csv(matrix):
    if not isinstance(matrix, dict):
        raise ValueError('Invalid matrix payload.')

    models = matrix.get('models')
    antibiotics = matrix.get('antibiotics')
    data = matrix.get('data')

    if not all(isinstance(value, list) for value in [models, antibiotics, data]):
        raise ValueError('Invalid matrix structure.')

    if len(antibiotics) != len(data):
        raise ValueError('Matrix data size mismatch.')

    for row in data:
        if not isinstance(row, list) or len(row) != len(models):
            raise ValueError('Matrix rows must match models length.')

    rows = []

    for antibiotic, values in zip(antibiotics, data):
        row_values = []

        for value in values:
            if value in (None, 'NO_RESULT'):
                row_values.append('')
                continue

            try:
                row_values.append(round(float(value), 4))
            except (ValueError, TypeError):
                row_values.append('')

        numeric_values = [value for value in row_values if value != '']

        average = (round(sum(numeric_values) / len(numeric_values), 4)
            if numeric_values else ''
        )

        rows.append([antibiotic] + row_values + [average])

    return models, rows