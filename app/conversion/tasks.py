from celery import shared_task
from django.core.files.base import ContentFile
import json
import os
import logging
import requests
from .models import ConversionTask, FileUpload
from .bio_api_client import annotate_from_fasta, download_assembly_fasta_result, download_bakta_json_result, get_job_status, sequence_illumina, sequence_ont
from notifications.services import notify_user_server_busy, notify_user_conversion_complete, notify_user_conversion_failed, notify_user_conversion_started, notify_user_conversion_warning
from notifications.models import TaskNotification
from celery.exceptions import MaxRetriesExceededError
from .utils import delete_file_safely, find_latest_persisted_upload, get_result_filename_stem, read_persisted_upload_bytes
from .parsers import parse_file

logger = logging.getLogger(__name__)

class BioServiceConnectionError(Exception):
    """Raised when unable to reach bio service (network/timeout issues)"""
    pass

class BioServiceBusyError(Exception):
    """Raised when bio service responds with 503 (server busy)"""
    pass

def _cleanup_temp_fastq_inputs(task):
    """Remove temporary FASTQ files used as assembly inputs."""
    if not task or not task.input_path:
        return
    if not task.task_type.startswith("assembly_"):
        return

    for candidate in task.input_path.split(','):
        path = (candidate or '').strip()
        if not path:
            continue
        if 'uploads\\temp\\' in path or 'uploads/temp/' in path:
            delete_file_safely(path)


def _persist_assembly_fasta_output(task):
    """Download and persist assembled FASTA for assembly tasks."""
    if not task or not task.external_job_id:
        return
    if not task.task_type.startswith("assembly_"):
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

    task.output_path = file_upload.file.name
    task.save(update_fields=['output_path'])


def _persist_annotation_json_output(task, complete_version=False):
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

    file_upload = parse_file(
        "bakta_json",
        parsed_payload,
        source_file,
        user=task.user,
        options={"complete_version": complete_version},
    )
    
    if file_upload:
        task.output_path = file_upload.file.name
        task.save(update_fields=['output_path'])


def _ensure_in_app_notification(task, event_type, message):
    """Guarantee at least one in-app notification exists for task/event."""
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
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, max_retries=1000)
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
        task.status = "failed"
        task.save()
        notify_user_conversion_failed(task.user, task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_FAILED,
            "The conversion failed because the external job was not found on the bio service.",
        )
        return
    
    if status != task.status:
        logger.info(f"Task {task.external_job_id}: status changed from {task.status} to {status}")
        if status == "annotated" or status == "assembled":
            status = "completed"
        task.status = status
        task.save()

    if status == "completed":
        logger.info(f"Conversion completed for task: {task.external_job_id}")
        if task.task_type.startswith("assembly_"):
            try:
                _persist_assembly_fasta_output(task)
            except Exception as e:
                logger.error(f"Unable to persist assembled FASTA for {task.external_job_id}, will retry: {str(e)}")
                try:
                    self.retry(countdown=60)
                except MaxRetriesExceededError:
                    logger.error(f"Max retries exceeded while persisting FASTA for task: {task.external_job_id}")
                    task.status = "failed"
                    task.save()
                    notify_user_conversion_failed(task.user, task)
                return
            # TODO: Check it works
            if task.task_type.endswith("annotated"):
                try:
                    _persist_annotation_json_output(task, complete_version=complete_version)
                except Exception as e:
                    logger.error(f"Unable to auto-parse annotation JSON for auto-annotated assembly {task.external_job_id}: {str(e)}")
                    notify_user_conversion_warning(
                        task.user,
                        task,
                        "Assembly & annotation succeeded, but automatic result upload failed. Try uploading the Bakta JSON manually from your downloads.",
                    )
        elif task.task_type == "annotation":
            try:
                _persist_annotation_json_output(task, complete_version=complete_version)
            except Exception as e:
                logger.error(f"Unable to auto-parse annotation JSON for task {task.external_job_id}: {str(e)}")
                notify_user_conversion_warning(
                    task.user,
                    task,
                    "Annotation succeeded, but automatic result upload failed. Try uploading the Bakta JSON manually from your downloads.",
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
        logger.debug(f"Polling will retry in 60s for task {task.external_job_id}")
        self.retry(countdown=60)  # Retry after 60 seconds
    
    except MaxRetriesExceededError: # When retries are exhausted
        logger.error(f"Max retries exceeded for task: {task.external_job_id}")
        task.status = "failed"
        task.save()
        notify_user_conversion_failed(task.user, task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_FAILED,
            "The conversion task did not complete within the expected timeframe. The bio service may be experiencing issues. Please try again later.",
        )
        return

# TODO: Por ahora aguanta máx 100 minutos, ver si es suficiente   
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_start(self, fasta_bytes, task_id, dest_path=None, user_id=None, complete_version=False):
    logger.info(f"Trying to start annotation task (task_id={task_id})")
    try:
        task = ConversionTask.objects.get(id=task_id)
    except ConversionTask.DoesNotExist:
        logger.error(f"Task not found when starting annotation: {task_id}")
        notify_user_conversion_failed(None, message="Task not found when starting annotation", task=None)
        return
    
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
                "Your annotation task has started processing on the bio service.",
            )
        poll_conversion_status.delay(task.id, complete_version=complete_version)
        return

    logger.info(f"Server busy response received for task {task_id}, will retry later")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        logger.error(f"Max retries exhausted starting annotation for task {task_id}")
        notify_user_server_busy(task.user if task else None, task=task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_WARNING,
            "The conversion server is busy. Please retry later.",
        )
        return

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_assembly_start(self, assembly_type="", dest_path=None, dest_path_2=None, annotate=False, task_id=None, user_id=None, complete_version=False):
    logger.info(f"Trying to start assembly task ({assembly_type}) for uploaded FASTQ")

    task = ConversionTask.objects.filter(id=task_id).first() if task_id else None
    effective_user = task.user if task else None
    combined_input_path = dest_path + ("," + dest_path_2 if dest_path_2 else "")
    assembly_task_type = "assembly" + ("_" + assembly_type) + ("_annotated" if annotate else "")

    if assembly_type not in ["illumina", "ont"]:
        logger.error(f"Invalid assembly type: {assembly_type}")
        notify_user_conversion_failed(effective_user, task=task, message="Invalid assembly type")
        return

    # Read files
    try:
        with open(dest_path, 'rb') as f:
            fastq_bytes = f.read()
    except Exception as e:
        logger.error(f"Failed to read fastq file from path {dest_path}: {str(e)}")
        if task:
            task.status = "failed"
            task.save(update_fields=['status'])
        notify_user_conversion_failed(effective_user, task=task, message="Failed to read fastq file")
        return

    # Illumina
    if assembly_type == "illumina":
        if not dest_path_2:
            logger.error(f"Illumina assembly requires second FASTQ but dest_path_2 is missing for task {task_id}")
            if task:
                task.status = "failed"
                task.save(update_fields=['status'])
            notify_user_conversion_failed(effective_user, task=task, message="Missing second FASTQ for Illumina")
            return
        try:
            with open(dest_path_2, 'rb') as f2:
                fastq_2_bytes = f2.read()
        except Exception as e:
            logger.error(f"Failed to read second fastq file from path {dest_path_2}: {str(e)}")
            if task:
                task.status = "failed"
                task.save(update_fields=['status'])
            notify_user_conversion_failed(effective_user, task=task, message="Failed to read second fastq file")
            return
        
        try:
            external_resp = sequence_illumina(fastq_bytes, fastq_2_bytes, annotate=annotate)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.warning(f"Connection error starting Illumina assembly for task {task_id}: {str(e)}")
            raise
    
    #ONT
    elif assembly_type == "ont":
        try:
            external_resp = sequence_ont(fastq_bytes, annotate=annotate)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.warning(f"Connection error starting ONT assembly for task {task_id}: {str(e)}")
            raise

    # Check response and update task
    if external_resp.get("status") in {"running", "pending"}:
        logger.info(f"Assembly started with job ID: {external_resp.get('job_id')} for task {task_id}")
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
                    f"Your {assembly_type.upper()} assembly task has started processing.",
                )
        else:
            first_input = (combined_input_path or '').split(',')[0].strip()
            task = ConversionTask.objects.create(
                external_job_id=external_resp["job_id"],
                status="running",
                input_path=combined_input_path,
                task_type=assembly_task_type,
                user_id=user_id,
                process_name=os.path.basename(first_input) if first_input else f"Process {external_resp['job_id']}",
            )
            notify_user_conversion_started(task.user, task)
            _ensure_in_app_notification(
                task,
                TaskNotification.EVENT_STARTED,
                f"Your {assembly_type.upper()} assembly task has started processing.",
            )
        poll_conversion_status.delay(task.id, complete_version=complete_version)
        return

    logger.info(f"Server busy response received for assembly task {task_id}, will retry later")
    try:
        self.retry(countdown=60)  # Retry after 60 seconds
    except MaxRetriesExceededError: # When retries are exhausted
        logger.error(f"Max retries exhausted starting assembly for task {task_id}")
        notify_user_server_busy(effective_user, task=task)
        _ensure_in_app_notification(
            task,
            TaskNotification.EVENT_WARNING,
            "The bioservice server is busy. Please retry later.",
        )
        return

    
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=1, max_retries=100)
def poll_annotation_from_assembly_start(self, job_id, user_id, new_task_id=None, complete_version=False):
    logger.info(f"Trying to start annotation task for assembly job {job_id} (new_task_id={new_task_id})")

    pending_task = ConversionTask.objects.filter(id=new_task_id).first() if new_task_id else None
    pending_user = pending_task.user if pending_task else None

    def _fail_pending_annotation(message):
        logger.error(f"Annotation task {new_task_id} failed: {message}")
        notify_user_conversion_failed(
            pending_user,
            task=pending_task,
            message=message,
        )
        if pending_task:
            pending_task.status = "failed"
            pending_task.save(update_fields=['status'])

    previous_job_qs = ConversionTask.objects.filter(
        external_job_id=job_id,
        task_type__startswith="assembly_",
        status="completed"
    )
    previous_job_qs = previous_job_qs.filter(user_id=user_id)

    previous_task = previous_job_qs.first()
    if not previous_task:
        logger.error(f"Previous assembly job not found for annotation task with job ID: {job_id}")
        _fail_pending_annotation(
            "The previous assembly job could not be found. Make sure it completed successfully before starting annotation."
        )
        return

    retrieval_error_message = "The assembled FASTA result is not available in the system. Try again later."
    try:
        fasta_bytes = read_persisted_upload_bytes(
            user_id=previous_task.user_id,
            filename_stem=get_result_filename_stem("assembly", previous_task.external_job_id),
        )
    except Exception as e:
        logger.error(f"Failed to read persisted FASTA file for previous task {previous_task.id}: {str(e)}")
        _fail_pending_annotation(retrieval_error_message)
        return

    if fasta_bytes is None or not fasta_bytes:
        _fail_pending_annotation(retrieval_error_message)
        return


    poll_annotation_start.delay(
        fasta_bytes=fasta_bytes,
        task_id=new_task_id,
        user_id=user_id,
        complete_version=complete_version,
    )
