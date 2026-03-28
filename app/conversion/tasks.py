from celery import shared_task
import requests
from django.core.files.base import ContentFile
from .models import ConversionTask, FileUpload
from .services import annotate_from_fasta, annotate_from_sequencing_job, download_assembly_fasta_result, get_job_status, sequence_illumina, sequence_ont
from notifications.services import notify_user_server_busy, notify_user_conversion_complete, notify_user_conversion_failed
from celery.exceptions import MaxRetriesExceededError
from .utils import delete_file_safely


def _cleanup_temp_fastq_inputs(task):
    """Remove temporary FASTQ files used as sequencing inputs."""
    if not task or not task.input_path:
        return
    if not task.task_type.startswith("sequencing_"):
        return

    for candidate in task.input_path.split(','):
        path = (candidate or '').strip()
        if not path:
            continue
        if 'uploads\\temp\\' in path or 'uploads/temp/' in path:
            delete_file_safely(path)


def _persist_sequencing_fasta_output(task):
    """Download and persist assembled FASTA for sequencing tasks."""
    if not task or not task.external_job_id:
        return
    if not task.task_type.startswith("sequencing_"):
        return

    filename = f"assembly_{task.external_job_id}.fasta"
    if FileUpload.objects.filter(user_id=task.user_id, file__contains=filename).exists():
        return

    fasta_content = download_assembly_fasta_result(task.external_job_id)
    if not fasta_content:
        raise ValueError("Downloaded FASTA content is empty")
    file_upload = FileUpload(user_id=task.user_id)
    file_upload.file.save(filename, ContentFile(fasta_content), save=True)

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente
# TODO: Cambiar notificaciones para que sean a usuarios
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, max_retries=100)
def poll_conversion_status(self, task_id):
    try:
        task = ConversionTask.objects.get(id=task_id)
    except ConversionTask.DoesNotExist:
        # If some task is missing, just stop polling
        return

    print("Polling status for task:", task.external_job_id)

    status, code = get_job_status(task.external_job_id)

    if code == 404:
        print("Job not found for task:", task.external_job_id)
        task.status = "failed"
        task.save()
        notify_user_conversion_failed(task.user, task)
        return
    
    if status != task.status:
        print("Status changed from", task.status, "to", status)
        if status == "annotated" or status == "assembled":
            status = "completed"
        task.status = status
        task.save()

    if status == "completed":
        print("Conversion completed for task:", task.external_job_id)
        if task.task_type.startswith("sequencing_"):
            try:
                _persist_sequencing_fasta_output(task)
            except Exception as e:
                print("Unable to persist assembled FASTA, will retry:", str(e))
                try:
                    self.retry(countdown=60)
                except MaxRetriesExceededError:
                    print("Max retries exceeded while persisting FASTA for task:", task.external_job_id)
                    task.status = "failed"
                    task.save()
                    notify_user_conversion_failed(task.user, task)
                return
        _cleanup_temp_fastq_inputs(task)
        notify_user_conversion_complete(task.user, task)
        return

    if status == "failed":
        notify_user_conversion_failed(task.user, task)
        return

    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    
    except MaxRetriesExceededError: # When retries are exhausted
        print("Max retries exceeded for task:", task.external_job_id)
        task.status = "failed"
        task.save()
        notify_user_conversion_failed(task.user, task)
        return

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente   
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_start(self, fasta_bytes, dest_path=None, task_id=None, user_id=None):
    
    print("Trying to start annotation task for uploaded FASTA")
    task = ConversionTask.objects.filter(id=task_id).first() if task_id else None
    external_resp = annotate_from_fasta(fasta_bytes)

    if external_resp.get("status") == "running" or external_resp.get("status") == "annotation_pending":
        print("Annotation started with job ID:", external_resp["job_id"])
        if task_id:
            try:
                task = ConversionTask.objects.get(id=task_id)
                if user_id is None:
                    user_id = task.user_id
                task.external_job_id = external_resp["job_id"]
                task.status = "running"
                task.save()
            except ConversionTask.DoesNotExist:
                task = ConversionTask.objects.create(
                    external_job_id=external_resp["job_id"],
                    status="running",
                    input_path=dest_path,
                    task_type="annotation",
                    user_id=user_id
                )
        else:
            task = ConversionTask.objects.create(
                external_job_id=external_resp["job_id"],
                status="running",
                input_path=dest_path,
                task_type="annotation",
                user_id=user_id
            )
        poll_conversion_status.delay(task.id)
        return

    print("Server busy response received, will retry later.")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        notify_user_server_busy(task.user if task else None, task=task)
        return

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_sequencing_start(self, sequencing_type="", dest_path=None, dest_path_2=None, annotate=False, task_id=None, user_id=None):

    print("Trying to start sequencing task for uploaded FASTQ (reading from disk)")

    task = ConversionTask.objects.filter(id=task_id).first() if task_id else None
    effective_user = task.user if task else None

    if sequencing_type not in ["illumina", "ont"]:
        notify_user_conversion_failed(effective_user, task=task, message="Invalid sequencing type")
        return

    # Read files
    try:
        with open(dest_path, 'rb') as f:
            fastq_bytes = f.read()
    except Exception as e:
        print("Failed to read fastq file from path:", dest_path, str(e))
        notify_user_conversion_failed(effective_user, task=task, message="Failed to read fastq file")
        return

    # Illumina
    if sequencing_type == "illumina":
        if not dest_path_2:
            print("Illumina sequencing requires a second FASTQ file but dest_path_2 is missing")
            notify_user_conversion_failed(effective_user, task=task, message="Missing second FASTQ for Illumina")
            return
        try:
            with open(dest_path_2, 'rb') as f2:
                fastq_2_bytes = f2.read()
        except Exception as e:
            print("Failed to read second fastq file from path:", dest_path_2, str(e))
            notify_user_conversion_failed(effective_user, task=task, message="Failed to read second fastq file")
            return
        
        external_resp = sequence_illumina(fastq_bytes, fastq_2_bytes, annotate=annotate)
    
    #ONT
    elif sequencing_type == "ont":
        external_resp = sequence_ont(fastq_bytes, annotate=annotate)

    if external_resp.get("status") == "running" or external_resp.get("status") == "pending":
        print("Sequencing started with job ID:", external_resp["job_id"])
        if task_id:
            try:
                task = ConversionTask.objects.get(id=task_id)
                if user_id is None:
                    user_id = task.user_id
                task.external_job_id = external_resp["job_id"]
                task.status = "running"
                task.save()
            except ConversionTask.DoesNotExist:
                task = ConversionTask.objects.create(
                    external_job_id=external_resp["job_id"],
                    status="running",
                    input_path=dest_path + ("," + dest_path_2 if dest_path_2 else ""),
                    task_type="sequencing" + ("_" + sequencing_type) + ("_annotated" if annotate else ""),
                    user_id=user_id
                )
        else:
            task = ConversionTask.objects.create(
                external_job_id=external_resp["job_id"],
                status="running",
                input_path=dest_path + ("," + dest_path_2 if dest_path_2 else ""),
                task_type="sequencing" + ("_" + sequencing_type) + ("_annotated" if annotate else ""),
                user_id=user_id
            )
        poll_conversion_status.delay(task.id)
        return

    print("Server busy response received, will retry later.")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        notify_user_server_busy(effective_user, task=task)
        return
    
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_from_sequencing_start(self, job_id, new_task_id=None, user_id=None):
    print("Trying to start annotation task for uploaded FASTA")

    if user_id is None and new_task_id:
        pending_task = ConversionTask.objects.filter(id=new_task_id).first()
        if pending_task:
            user_id = pending_task.user_id
    
    previous_job_qs = ConversionTask.objects.filter(external_job_id=job_id)
    if user_id:
        previous_job_qs = previous_job_qs.filter(user_id=user_id)

    previous_job = previous_job_qs.first()
    if not previous_job:
        print("Previous sequencing job not found for annotation task with job ID:", job_id)
        pending_task = ConversionTask.objects.filter(id=new_task_id).first() if new_task_id else None
        notify_user_conversion_failed(
            pending_task.user if pending_task else None,
            task=pending_task,
            message="Previous sequencing job not found",
        )
        return

    if previous_job.status != "completed":
        print("Previous sequencing job is not completed yet, will retry. Status:", previous_job.status)
        pending_task = ConversionTask.objects.filter(id=new_task_id).first() if new_task_id else None
        notify_user_conversion_failed(
            pending_task.user if pending_task else None,
            task=pending_task,
            message="Previous sequencing job is not completed yet. Please wait a bit and try again.",
        )
        return
    
    external_resp = annotate_from_sequencing_job(job_id)

    if external_resp.get("status") == "running" or external_resp.get("status") == "annotation_pending":
        print("Annotation started with job ID:", external_resp["job_id"])
        if new_task_id:
            try:
                task = ConversionTask.objects.get(id=new_task_id)
                task.external_job_id = external_resp["job_id"]
                task.status = "running"
                task.input_path = previous_job.input_path
                task.save()
            except ConversionTask.DoesNotExist:
                task = ConversionTask.objects.create(
                    external_job_id=external_resp["job_id"],
                    status="running",
                    input_path=previous_job.input_path,
                    task_type="annotation",
                    user_id=user_id
                )
        else:
            task = ConversionTask.objects.create(
                external_job_id=external_resp["job_id"],
                status="running",
                input_path=previous_job.input_path,
                task_type="annotation",
                user_id=user_id
            )
        poll_conversion_status.delay(task.id)
        return

    print("Server busy response received, will retry later.")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        task = ConversionTask.objects.filter(id=new_task_id).first() if new_task_id else None
        notify_user_server_busy(task.user if task else None, task=task)
        return
