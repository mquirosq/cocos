from celery import shared_task

from core.models import File, TaskStatus
from .models import PredictionTask
from .prediction import get_prediction_matrix, prepare_prediction_csv, create_prediction_csv

@shared_task(bind=True)
def predict(self, task_id: int, file_id: int) -> dict:
    task = PredictionTask.objects.get(pk=task_id)
    file = File.objects.get(pk=file_id)

    task.status = TaskStatus.RUNNING
    task.save(update_fields=['status', 'updated_at'])

    try:
        matrix = get_prediction_matrix(task.selected_models, task.selected_antibiotics, file)

        task.data = matrix['data']

        models, rows = prepare_prediction_csv(matrix)

        csv_file = create_prediction_csv(task=task, models=models, rows=rows)

        task.output_csv = csv_file
        task.status = TaskStatus.COMPLETED
        task.save(update_fields=['status', 'data', 'output_csv', 'updated_at'])

        return matrix
    
    except Exception:
        task.status = TaskStatus.FAILED
        task.save(update_fields=['status', 'updated_at'])
        raise