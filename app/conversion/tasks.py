from celery import shared_task
from django.core.files.base import ContentFile
import json
from .models import ConversionTask, FileUpload
from .services import annotate_from_fasta, download_assembly_fasta_result, download_bakta_json_result, get_job_status, sequence_illumina, sequence_ont
from notifications.services import notify_user_server_busy, notify_user_conversion_complete, notify_user_conversion_failed, notify_user_conversion_started, notify_user_conversion_warning
from notifications.models import TaskNotification
from celery.exceptions import MaxRetriesExceededError
from .utils import delete_file_safely, find_latest_persisted_upload, get_result_filename_stem, read_persisted_upload_bytes
from .parsers import parse_file


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

    filename_stem = get_result_filename_stem("assembly", task.external_job_id)
    filename = f"{filename_stem}.fasta"
    if find_latest_persisted_upload(user_id=task.user_id, filename_stem=filename_stem):
        return

    fasta_content = download_assembly_fasta_result(task.external_job_id)
    if not fasta_content:
        raise ValueError("Downloaded FASTA content is empty")
    file_upload = FileUpload(user_id=task.user_id)
    file_upload.file.save(filename, ContentFile(fasta_content), save=True)


def _persist_annotation_json_output(task):
    """Download Bakta JSON and parse it into DB entities for annotation tasks."""
    if not task or not task.external_job_id or task.task_type != "annotation":
        return

    filename_stem = get_result_filename_stem("annotation", task.external_job_id)
    if find_latest_persisted_upload(user_id=task.user_id, filename_stem=filename_stem):
        return

    json_result = download_bakta_json_result(task.external_job_id)
    if isinstance(json_result, list):
        parsed_payload = {"features": json_result}
    elif isinstance(json_result, dict):
        parsed_payload = json_result
    else:
        raise ValueError("Downloaded annotation payload has invalid format")

    filename = f"{filename_stem}.json"
    json_bytes = json.dumps(parsed_payload).encode("utf-8")
    source_file = ContentFile(json_bytes, name=filename)

    parse_file(
        "bakta_json",
        parsed_payload,
        source_file,
        user=task.user,
        options={"complete_version": True},
    )


def _ensure_in_app_notification(task, event_type, message):
    """Guarantee at least one in-app notification exists for task/event."""
    # TODO: return and reload celery to check if notis are ok
    if not task or not task.user_id:
        return

    already_exists = TaskNotification.objects.filter(
        task=task,
        user_id=task.user_id,
        event_type=event_type,
    ).exists()
    if already_exists:
        return

    TaskNotification.objects.create(
        user_id=task.user_id,
        task=task,
        event_type=event_type,
        message=message,
        channels=[TaskNotification.CHANNEL_IN_APP],
    )

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente
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
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_FAILED,
            "The conversion failed because the external job was not found.",
        )
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
        elif task.task_type == "annotation":
            try:
                _persist_annotation_json_output(task)
            except Exception as e:
                print("Unable to auto-parse annotation JSON:", str(e))
                notify_user_conversion_warning(
                    task.user,
                    task,
                    "Annotation finished, but automatic DB ingestion failed. Upload the Bakta JSON in Annotation > Bakta JSON to DB to retry.",
                )
        _cleanup_temp_fastq_inputs(task)
        notify_user_conversion_complete(task.user, task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_COMPLETED,
            "The conversion task completed. You can review outputs from Tasks.",
        )
        return

    if status == "failed":
        notify_user_conversion_failed(task.user, task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_FAILED,
            "The conversion task failed. Please review logs and retry.",
        )
        return

    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    
    except MaxRetriesExceededError: # When retries are exhausted
        print("Max retries exceeded for task:", task.external_job_id)
        task.status = "failed"
        task.save()
        notify_user_conversion_failed(task.user, task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_FAILED,
            "The conversion task failed after maximum polling retries.",
        )
        return

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente   
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_start(self, fasta_bytes, task_id, dest_path=None, user_id=None):
    print("Trying to start annotation task for uploaded FASTA")
    try:
        task = ConversionTask.objects.get(id=task_id)
    except ConversionTask.DoesNotExist:
        notify_user_conversion_failed(None, message="Task not found when starting annotation", task=None)
        return
    
    external_resp = annotate_from_fasta(fasta_bytes)

    if external_resp.get("status") == "running" or external_resp.get("status") == "annotation_pending":
        print("Annotation started with job ID:", external_resp["job_id"])
        if user_id is None:
            user_id = task.user_id
        should_notify_started = task.status != "running"
        task.external_job_id = external_resp["job_id"]
        task.status = "running"
        task.save()
        if should_notify_started:
            notify_user_conversion_started(task.user, task)
            _ensure_in_app_notification(
                task,
                TaskNotification.EVENT_STARTED,
                "The conversion task has started and is currently running.",
            )
        poll_conversion_status.delay(task.id)
        return

    print("Server busy response received, will retry later.")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        notify_user_server_busy(task.user if task else None, task=task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_WARNING,
            "The conversion server is busy. Please retry later.",
        )
        return

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_sequencing_start(self, sequencing_type="", dest_path=None, dest_path_2=None, annotate=False, task_id=None, user_id=None):
    print("Trying to start sequencing task for uploaded FASTQ (reading from disk)")

    task = ConversionTask.objects.filter(id=task_id).first() if task_id else None
    effective_user = task.user if task else None
    combined_input_path = dest_path + ("," + dest_path_2 if dest_path_2 else "")
    sequencing_task_type = "sequencing" + ("_" + sequencing_type) + ("_annotated" if annotate else "")

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

    # Check response and update task
    if external_resp.get("status") in {"running", "pending"}:
        print("Sequencing started with job ID:", external_resp["job_id"])
        if task:
            if user_id is None:
                user_id = task.user_id
            should_notify_started = task.status != "running"
            task.external_job_id = external_resp["job_id"]
            task.status = "running"
            task.save()
            if should_notify_started:
                notify_user_conversion_started(task.user, task)
                _ensure_in_app_notification(
                    task,
                    TaskNotification.EVENT_STARTED,
                    "The conversion task has started and is currently running.",
                )
        else:
            task = ConversionTask.objects.create(
                external_job_id=external_resp["job_id"],
                status="running",
                input_path=combined_input_path,
                task_type=sequencing_task_type,
                user_id=user_id,
            )
            notify_user_conversion_started(task.user, task)
            _ensure_in_app_notification(
                task,
                TaskNotification.EVENT_STARTED,
                "The conversion task has started and is currently running.",
            )
        poll_conversion_status.delay(task.id)
        return

    print("Server busy response received, will retry later.")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        notify_user_server_busy(effective_user, task=task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_WARNING,
            "The conversion server is busy. Please retry later.",
        )
        return

    
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_from_sequencing_start(self, job_id, user_id, new_task_id=None):
    print("Trying to start annotation task for uploaded FASTA")

    pending_task = ConversionTask.objects.filter(id=new_task_id).first() if new_task_id else None
    pending_user = pending_task.user if pending_task else None

    def _fail_pending_annotation(message):
        notify_user_conversion_failed(
            pending_user,
            task=pending_task,
            message=message,
        )

    previous_job_qs = ConversionTask.objects.filter(
        external_job_id=job_id,
        task_type__startswith="sequencing_",
        status="completed"
    )
    previous_job_qs = previous_job_qs.filter(user_id=user_id)

    previous_task = previous_job_qs.first()
    if not previous_task:
        print("Previous sequencing job not found for annotation task with job ID:", job_id)
        _fail_pending_annotation(
            "Invalid previous sequencing job. Please make sure the sequencing task has completed successfully before starting annotation."
        )
        return

    retrieval_error_message = "Could not retrieve assembled FASTA from persistent uploads for the previous sequencing task."
    try:
        fasta_bytes = read_persisted_upload_bytes(
            user_id=previous_task.user_id,
            filename_stem=get_result_filename_stem("assembly", previous_task.external_job_id),
        )
    except Exception as e:
        print("Failed to read persisted FASTA file:", str(e))
        _fail_pending_annotation(retrieval_error_message)
        return

    if fasta_bytes is None or not fasta_bytes:
        _fail_pending_annotation(retrieval_error_message)
        return


    poll_annotation_start.delay(
        fasta_bytes=fasta_bytes,
        task_id=new_task_id,
        user_id=user_id,
    )