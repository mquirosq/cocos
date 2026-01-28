from celery import shared_task
from .models import AnnotationTask
from .services import get_job_status, download_bakta_json_result
from .notification import notify_user_annotation_complete, notify_user_annotation_failed

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10)
def poll_external_task(self, task_id):
    task = AnnotationTask.objects.get(id=task_id)

    status = get_job_status(task.external_job_id)

    if status != task.status:
        task.status = status
        task.save()

    if status == "completed":
        download_bakta_json_result(task.external_job_id)
        notify_user_annotation_complete(task.user, task)
        return

    if status == "failed":
        notify_user_annotation_failed(task.user, task)
        return

    self.retry(countdown=30)
