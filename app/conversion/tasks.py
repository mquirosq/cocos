from celery import shared_task
from django.core.files.base import ContentFile
import json
import logging
import requests
from .models import ConversionTask, File, ProcessGroup
from .bio_api_client import annotate_from_fasta, download_assembly_fasta_result, download_bakta_json_result, get_job_status, sequence_illumina, sequence_ont
from notifications.services import notify_user_server_busy, notify_user_conversion_complete, notify_user_conversion_failed, notify_user_conversion_started, notify_user_conversion_warning
from notifications.models import TaskNotification
from celery.exceptions import MaxRetriesExceededError
from .utils import get_result_filename_stem, upload_file
from .parsers import parse_file
from .task_types import ASSEMBLY_TYPES, ANNOTATED_TYPES

logger = logging.getLogger(__name__)

MAX_TRIES = 100

def _persist_assembly_fasta_output(task):
    """Download and persist the assembled FASTA for an assembly task."""
    if not task or not task.external_job_id or not task.task_type.startswith("assembly_") or task.output_files.exists():
        return

    filename_stem = get_result_filename_stem("assembly", task.external_job_id)
    filename = f"{filename_stem}.fasta"

    fasta_content = download_assembly_fasta_result(task.external_job_id)
    if not fasta_content:
        raise ValueError("Downloaded FASTA content is empty")

    file = upload_file(ContentFile(fasta_content, name=filename), task.process.user, File.FileType.FASTA,)

    task.output_files.add(file)
    task.save(update_fields=["updated_at"])


def _persist_annotation_json_output(task, complete_version=False):
    """Download and persist the Bakta JSON for an annotation task."""
    if (not task or not task.external_job_id
        or task.task_type not in ANNOTATED_TYPES
        or task.output_files.filter(file_type=File.FileType.JSON).exists()):
        return
    
    filename_stem = get_result_filename_stem(
        "annotation",
        task.external_job_id,
    )
    filename = f"{filename_stem}.json"

    json_result = download_bakta_json_result(task.external_job_id)

    if isinstance(json_result, list):
        parsed_payload = {"features": json_result}
    elif isinstance(json_result, dict):
        parsed_payload = json_result
    else:
        raise ValueError("Downloaded annotation payload has invalid format")

    source_file = ContentFile(json.dumps(parsed_payload).encode("utf-8"), name=filename)

    file = upload_file(source_file, task.process.user, File.FileType.JSON)

    file = parse_file(parser="bakta_json", data=parsed_payload, file=file, user=task.process.user, options={"complete_version": complete_version})

    if file:
        task.output_files.add(file)
        task.save(update_fields=["updated_at"])

def _ensure_in_app_notification(task, event_type, message):
    """Guarantee at least one in-app notification exists for task/event."""
    if not task or not task.process.user.id:
        return

    already_exists = TaskNotification.objects.filter(
        task=task,
        user_id=task.process.user.id,
        event_type=event_type,
    ).exists()
    if already_exists:
        return

    TaskNotification.objects.create(
        user_id=task.process.user.id,
        task=task,
        event_type=event_type,
        message=message,
        channels=[TaskNotification.CHANNEL_IN_APP],
    )

def _fail_task(task, message):
    """Mark a task as failed and notify the user."""
    if not task:
        notify_user_conversion_failed(None, task=None, message=message)
        return

    logger.error(
        f"Task {task.id} ({task.task_type}) failed: {message}"
    )

    task.status = ConversionTask.TaskStatus.FAILED
    task.save(update_fields=["status"])

    notify_user_conversion_failed(
        task.process.user,
        task=task,
        message=message,
    )

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, max_retries=MAX_TRIES)
def poll_conversion_status(self, task_id, complete_version=False):
    try:
        task = ConversionTask.objects.get(id=task_id)
    except ConversionTask.DoesNotExist:
        # If some task is missing, just stop polling
        logger.info(f"Task {task_id} not found, stopping poll")
        return

    logger.debug(f"Polling status for task: {task.external_job_id} (task_id={task_id})")

    status, code = get_job_status(task.external_job_id)

    if code == 404:
        logger.warning(f"External job not found: {task.external_job_id}")
        _fail_task(task, "External job not found")
        return
        
    if status != task.status:
        logger.info(f"Task {task.external_job_id}: status changed from {task.status} to {status}")
        if status == "annotated" or status == "assembled":
            status = "completed"
        task.status = status
        task.save()

    if status == "completed":
        logger.info(f"Conversion completed for task: {task.external_job_id}")
        if task.task_type in ASSEMBLY_TYPES:
            try:
                _persist_assembly_fasta_output(task)
            except Exception as e:
                logger.error(f"Unable to persist assembled FASTA for {task.external_job_id}, will retry: {str(e)}")
                try:
                    self.retry(countdown=60)
                except MaxRetriesExceededError:
                    logger.error(f"Max retries exceeded while persisting FASTA for task: {task.external_job_id}")
                    _fail_task(task, "Max retries exceeded while persisting FASTA")
                return
        if task.task_type in ANNOTATED_TYPES:
            try:
                _persist_annotation_json_output(task, complete_version=complete_version)
            except Exception as e:
                logger.error(f"Unable to auto-parse annotation JSON for task {task.external_job_id}: {str(e)}")
                notify_user_conversion_warning(task.process.user, task, "Annotation succeeded, but automatic result upload failed. Try uploading the Bakta JSON manually from your downloads.")
        notify_user_conversion_complete(task.process.user, task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_COMPLETED,
            "The conversion task completed. You can review outputs from Tasks.",
        )
        return

    if status == "failed":
        _fail_task(task, "External job failed")
        return

    try:
        logger.debug(f"Polling will retry in 60s for task {task.external_job_id}")
        self.retry(countdown=60)  # Retry after 60 seconds
    
    except MaxRetriesExceededError: # When retries are exhausted
        logger.error(f"Max retries exceeded for task: {task.external_job_id}")
        _fail_task(task, "Max retries exceeded while polling status")
        return

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=MAX_TRIES)
def poll_annotation_start(self, task_id, complete_version=False):
    logger.info(f"Trying to start annotation task (task_id={task_id})")
    try:
        task = ConversionTask.objects.get(id=task_id)
    except ConversionTask.DoesNotExist:
        logger.error(f"Task not found when starting annotation: {task_id}")
        _fail_task(None, "Task not found when starting annotation")
        return

    fasta_file = task.input_files.filter(file_type=File.FileType.FASTA).first()

    if not fasta_file:
        logger.error(f"No FASTA input found for annotation task {task_id}")
        task.status = ConversionTask.TaskStatus.FAILED
        task.save(update_fields=['status'])

        _fail_task(task, "No FASTA input was found for the annotation task.")
        return

    with fasta_file.file.open('rb') as f:
        fasta_bytes = f.read()

    try:
        external_resp = annotate_from_fasta(fasta_bytes)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logger.warning(f"Connection error starting annotation for task {task_id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting annotation for task {task_id}: {str(e)}")
        raise

    if external_resp.get("status") == "running" or external_resp.get("status") == "annotation_pending":
        logger.info(f"Annotation started with job ID: {external_resp.get('job_id')} for task {task_id}")
        should_notify_started = task.status != ConversionTask.TaskStatus.RUNNING
        task.external_job_id = external_resp["job_id"]
        task.status = ConversionTask.TaskStatus.RUNNING
        task.save()
        if should_notify_started:
            notify_user_conversion_started(task.process.user, task)
            _ensure_in_app_notification(task, TaskNotification.EVENT_STARTED, "Your annotation task has started processing on the bio service.")
        poll_conversion_status.delay(task.id, complete_version=complete_version)
        return

    logger.info(f"Server busy response received for task {task_id}, will retry later")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        logger.error(f"Max retries exhausted starting annotation for task {task_id}")
        notify_user_server_busy(task.process.user if task else None, task=task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_WARNING,
            "The conversion server is busy. Please retry later.",
        )
        return

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=MAX_TRIES)
def poll_assembly_start(self, task_id=None, assembly_type=None, annotate=False, complete_version=False,):
    logger.info(f"Trying to start assembly task (task_id={task_id}, assembly_type={assembly_type}, annotate={annotate}, complete_version={complete_version})")

    try:
        task = ConversionTask.objects.select_related(
            'process__user'
        ).get(id=task_id)
    except ConversionTask.DoesNotExist:
        logger.error(f"Task not found when starting assembly: {task_id}")
        return

    # Get the input FASTQ files
    file_1 = task.input_files.filter(
        file_type=File.FileType.FASTQ
    ).first()

    if not file_1:
        _fail_task(task, "No FASTQ input was found for the assembly task.")
        return

    try:
        with file_1.file.open("rb") as f:
            fastq_bytes = f.read()
    except Exception:
        _fail_task(task, "Failed to read FASTQ file.")
        return

    fastq_2_bytes = None

    if assembly_type == "illumina":
        file_2 = task.input_files.filter(file_type=File.FileType.FASTQ).exclude(id=file_1.id).first()

        if not file_2:
            _fail_task(task, "Missing second FASTQ for Illumina assembly.")
            return

        try:
            with file_2.file.open("rb") as f:
                fastq_2_bytes = f.read()
        except Exception:
            _fail_task(task, "Failed to read second FASTQ file.")
            return

    # Start assembly
    try:
        if assembly_type == "illumina":
            external_resp = sequence_illumina(fastq_bytes, fastq_2_bytes, annotate=annotate)

        elif assembly_type == "ont":
            external_resp = sequence_ont(fastq_bytes, annotate=annotate)

        else:
            _fail_task(task, f"Invalid assembly type: {assembly_type}")
            return

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logger.warning(f"Connection error starting assembly for task {task_id}")
        raise

    # Check response and update task
    if external_resp.get("status") in {"running", "pending"}:
        job_id = external_resp.get("job_id")

        logger.info(f"Assembly started with job ID: {job_id} for task {task_id}")

        should_notify_started = task.status != ConversionTask.TaskStatus.RUNNING

        task.external_job_id = job_id
        task.status = ConversionTask.TaskStatus.RUNNING
        task.save(update_fields=["external_job_id", "status"])

        if should_notify_started:
            notify_user_conversion_started(task.process.user, task)
            _ensure_in_app_notification(
                task,
                TaskNotification.EVENT_STARTED,
                f"Your {assembly_type.upper()} assembly task has started processing.",
            )

        poll_conversion_status.delay(task.id, complete_version=complete_version)
        return

    logger.info(f"Server busy response received for assembly task {task_id}, will retry later")

    try:
        self.retry(countdown=60)
    except MaxRetriesExceededError:
        logger.error(f"Max retries exhausted starting assembly for task {task_id}")
        notify_user_server_busy(task.process.user, task=task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_WARNING,
            "The bioservice server is busy. Please retry later.",
        )
        return
