from celery import shared_task

from core.models import File, TaskStatus
from .models import PredictionTask
from .prediction import get_prediction_matrix, prepare_prediction_csv, create_prediction_csv
from notifications.services import notify_user_server_busy, notify_user_conversion_complete, notify_user_conversion_failed, notify_user_conversion_started

@shared_task(bind=True)
def predict(self, task_id: int, file_id: int) -> dict:
    task = PredictionTask.objects.get(pk=task_id)
    file = File.objects.get(pk=file_id)

    task.status = TaskStatus.RUNNING
    task.save(update_fields=['status', 'updated_at'])

    notify_user_conversion_started(task.process.user, task, "The prediction task has started and is now running.")

    try:
        matrix = get_prediction_matrix(task.selected_models, task.selected_antibiotics, file)

        task.data = matrix['data']

        models, rows = prepare_prediction_csv(matrix)

        csv_file = create_prediction_csv(task=task, models=models, rows=rows)

        task.output_csv = csv_file
        task.status = TaskStatus.COMPLETED
        task.save(update_fields=['status', 'data', 'output_csv', 'updated_at'])
        notify_user_conversion_complete(task.process.user, task, "The prediction task has completed successfully. You can now access your results.")

        return matrix
    
    except Exception:
        task.status = TaskStatus.FAILED
        task.save(update_fields=['status', 'updated_at'])
        notify_user_conversion_failed(task.process.user, task, "The prediction task has failed. Please try again.")
        raise