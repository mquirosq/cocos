from celery import shared_task

from conversion.models import File
from .service import get_prediction_matrix

@shared_task(bind=True)
def predict(self, model_names: list[str], antibiotics: list[str], file_upload_id: int) -> dict:
    file_upload = File.objects.get(pk=file_upload_id)
    matrix = get_prediction_matrix(model_names, antibiotics, file_upload)
    return matrix
