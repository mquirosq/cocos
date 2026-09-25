from django.db import models

from conversion.models import File, ConversionTask
from conversion.services.presentation import format_process_label
from conversion.task_types import ANNOTATED_TYPES

from .registry import get_model_supported_antibiotics
from .tasks import predict


def get_prediction_input_options(user):
    tasks_json = ConversionTask.objects.filter(
        models.Q(task_type=ConversionTask.TaskType.FROM_JSON) |
        models.Q(task_type__in=ANNOTATED_TYPES),
        process__user=user,
    ).order_by('-created_at')
    options = []

    for task in tasks_json:

        json_file = None
        if task.task_type == ConversionTask.TaskType.FROM_JSON:
            json_file = task.input_files.filter(file_type=File.FileType.JSON).first()
        else: 
            json_file = task.output_files.filter(file_type=File.FileType.JSON).first()

        options.append({
                        'id': str(json_file.id) if json_file else None,
                        'label': format_process_label(task),
                    })

    return options

def start_prediction(user, model_names, antibiotics, file_id=None):
    if not model_names:
        raise ValueError('Select at least one model.')

    if not antibiotics:
        raise ValueError('Select at least one antibiotic.')

    file = None

    if file_id:
        try:
            file = File.objects.get(pk=int(file_id), user=user, file_type=File.FileType.JSON)
        except (ValueError, File.DoesNotExist):
            raise ValueError('Selected file not found.')

    valid_antibiotics = [antibiotic for antibiotic in antibiotics
        if any(antibiotic in get_model_supported_antibiotics(model_name) for model_name in model_names)
    ]

    if not valid_antibiotics:
        raise ValueError('No valid antibiotic/model combinations found.')

    # TODO: Make really async with Celery, for now sync
    return predict(
        model_names=model_names,
        antibiotics=valid_antibiotics,
        file_id=file.id if file else None,
    )

def prepare_prediction_csv(matrix):
    if not isinstance(matrix, dict):
        raise ValueError('Invalid matrix payload.')

    models = matrix.get('models')
    antibiotics = matrix.get('antibiotics')
    data = matrix.get('data')

    if not (isinstance(models, list) and isinstance(antibiotics, list) and isinstance(data, list)):
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
            if value is None:
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