from celery import shared_task

from conversion.models import File
from .prediction import get_prediction_matrix

@shared_task(bind=True)
def predict(self, model_names: list[str], antibiotics: list[str], file_id: int) -> dict:
    file = File.objects.get(pk=file_id)
    matrix = get_prediction_matrix(model_names, antibiotics, file)
    return matrix
