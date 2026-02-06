from celery import shared_task
from .models import AnnotationTask
from .services import annotate_from_fasta, get_job_status
from .notification import notify_user_annotation_complete, notify_user_annotation_failed, notify_user_server_busy
from celery.exceptions import MaxRetriesExceededError

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente
# TODO: Cambiar notificaciones para que sean a usuarios
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, max_retries=100)
def poll_annotation_status(self, task_id):
    try:
        task = AnnotationTask.objects.get(id=task_id)
    except AnnotationTask.DoesNotExist:
        # If some task is missing, just stop polling
        return

    print("Polling status for task:", task.external_job_id)

    status, code = get_job_status(task.external_job_id)

    if code == 404:
        print("Job not found for task:", task.external_job_id)
        task.status = "failed"
        task.save()
        notify_user_annotation_failed(None, task)
        return
    
    if status != task.status:
        print("Status changed from", task.status, "to", status)
        if status == "annotated":
            status = "completed"
        task.status = status
        task.save()

    if status == "completed":
        print("Annotation completed for task:", task.external_job_id)
        notify_user_annotation_complete(None, task)
        return

    if status == "failed":
        notify_user_annotation_failed(None, task)
        return

    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    
    except MaxRetriesExceededError: # When retries are exhausted
        print("Max retries exceeded for task:", task.external_job_id)
        task.status = "failed"
        task.save()
        notify_user_annotation_failed(None, task)
        return

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente   
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_start(self, fasta_bytes, dest_path=None):
    
    print("Trying to start annotation task for uploaded FASTA")
    external_resp = annotate_from_fasta(fasta_bytes)

    if external_resp.get("status") == "running" or external_resp.get("status") == "annotation_pending":
        print("Annotation started with job ID:", external_resp["job_id"])
        task = AnnotationTask.objects.create(
            external_job_id=external_resp["job_id"],
            status="running",
            input_path=dest_path
        )
        poll_annotation_status.delay(task.id)
        return

    print("Server busy response received, will retry later.")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        notify_user_server_busy(None)
        return
