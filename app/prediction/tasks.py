from celery import shared_task

from core.models import File, TaskStatus
from .models import PredictionTask
from .prediction import get_prediction_matrix

@shared_task(bind=True)
def predict(self, task_id: int, file_id: int) -> dict:
    task = PredictionTask.objects.get(pk=task_id)
    file = File.objects.get(pk=file_id)

    task.status = TaskStatus.RUNNING
    task.save(update_fields=['status', 'updated_at'])

    try:
        matrix = get_prediction_matrix(task.selected_models, task.selected_antibiotics, file)

        task.status = TaskStatus.COMPLETED
        task.data = matrix['data']
        task.save(update_fields=['status', 'data', 'updated_at'])

        return matrix
    
    except Exception:
        task.status = TaskStatus.FAILED
        task.save(update_fields=['status', 'updated_at'])
        raise