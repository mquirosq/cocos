import os

from .models import ConversionTask, FileUpload
from .presentation import format_source_job_label, pipeline_label, status_badge_class
from .utils import (
    get_primary_input_path,
    get_upload_dir,
    resolve_absolute_path,
    resolve_persisted_result_filename,
    source_filename,
    get_result_filename_stem,
)

ASSEMBLY_TYPES = {
    'sequencing_illumina',
    'sequencing_ont',
    'sequencing_illumina_annotated',
    'sequencing_ont_annotated',
}

FASTA_EXTENSIONS = {'.fa', '.fasta', '.fna', '.ffn', '.faa', '.frn'}

def resolve_uploaded_fasta_input_path(task):
    if not task or task.task_type != 'annotation' or task.previous_task_id:
        return None

    source = get_primary_input_path(task.input_path)
    if not source:
        return None

    if os.path.splitext(source.lower())[1] not in FASTA_EXTENSIONS:
        return None

    abs_source = resolve_absolute_path(source)

    expected_dir = os.path.normpath(get_upload_dir(task.user_id, 'fasta', persistent=True))
    normalized_source = os.path.normpath(abs_source)
    try:
        within_expected_dir = os.path.commonpath([normalized_source, expected_dir]) == expected_dir
    except ValueError:
        return None
    
    if not within_expected_dir:
        return None

    if not os.path.exists(abs_source):
        return None

    return abs_source


def annotation_process_key(task):
    return f"{task.process_name}::{task.input_path}"


def is_auto_annotated_assembly(task):
    return bool(task and task.task_type in {'sequencing_ont_annotated', 'sequencing_illumina_annotated'})


def find_latest_completed_annotation(annotations):
    for annotation in annotations:
        if annotation.status == 'completed':
            return annotation
    return None


def get_effective_annotation(annotations):
    """Return annotation to show in list cards.

    Prefer a completed annotation when available; otherwise show the newest attempt.
    """
    completed_annotation = find_latest_completed_annotation(annotations)
    if completed_annotation:
        return completed_annotation
    return annotations[0] if annotations else None


def find_annotation_with_uploaded_fasta(annotation_attempts):
    """Return the first annotation attempt that has a valid uploaded FASTA path."""
    for attempt in annotation_attempts:
        if resolve_uploaded_fasta_input_path(attempt):
            return attempt
    return None


def derive_process_name(task, fallback_name=None):
    if fallback_name:
        return fallback_name
    if task.previous_task_id and task.previous_task and task.previous_task.process_name:
        return task.previous_task.process_name
    if task.process_name:
        return task.process_name
    return source_filename(task.input_path)


def get_json_upload_for_task(task):
    # Annotation or auto-annotated assembly
    if getattr(task, 'external_job_id', None):
        user_id = task.user.id if hasattr(task.user, 'id') else task.user_id
        json_filename = resolve_persisted_result_filename(
            user_id=user_id,
            result_prefix='annotation',
            job_id=task.external_job_id,
        )
        if json_filename:
            if not json_filename.endswith('.json'):
                json_filename = json_filename + '.json'
            json_dir = get_upload_dir(user_id, 'json', persistent=True)
            json_path = os.path.join(json_dir, json_filename)
            if os.path.exists(json_path):
                return json_path

    # From-JSON tasks (uploaded JSON files)
    if task.input_path:
        upload = FileUpload.objects.filter(user=task.user, file=task.input_path).first()
        if upload:
            return upload
        file_name = os.path.basename(task.input_path)
        if file_name:
            return FileUpload.objects.filter(user=task.user, file__endswith=file_name).order_by('-uploaded_at').first()

    return None

def get_fasta_upload_for_task(task):
    """Return the absolute path to the FASTA file for a task, or None if not found."""
    task_type = getattr(task, 'task_type', None)
    if task_type == 'annotation':
        return resolve_uploaded_fasta_input_path(task)
    if task_type in ASSEMBLY_TYPES and getattr(task, 'external_job_id', None):
        user_id = getattr(getattr(task, 'user', None), 'id', None) or getattr(task, 'user_id', None)
        filename = f"{get_result_filename_stem('assembly', task.external_job_id)}.fasta"
        fasta_path = os.path.join(get_upload_dir(user_id, 'fasta', persistent=True), filename)
        return fasta_path if os.path.exists(fasta_path) else None
    return None


def build_process_rows(user):
    tasks = list(ConversionTask.objects.filter(user=user).select_related('previous_task').order_by('-updated_at', '-id'))

    sequencing_tasks = [task for task in tasks if task.task_type in ASSEMBLY_TYPES]
    sequencing_by_id = {task.id: task for task in sequencing_tasks}

    annotations_by_parent = {}
    standalone_annotations = {}
    json_tasks = {}

    for task in tasks:
        task.process_name = derive_process_name(task)
        if task.task_type == 'annotation' and task.previous_task_id in sequencing_by_id:
            annotations_by_parent.setdefault(task.previous_task_id, []).append(task)
        elif task.task_type == 'annotation' and task.previous_task_id is None:
            standalone_annotations.setdefault(annotation_process_key(task), []).append(task)
        elif task.task_type == 'from_json':
            json_tasks.setdefault(annotation_process_key(task), []).append(task)

    rows = []

    for sequencing_task in sequencing_tasks:
        annotations = sorted(annotations_by_parent.get(sequencing_task.id, []), key=lambda item: (item.updated_at, item.id), reverse=True)
        latest_annotation = annotations[0] if annotations else None
        latest_completed_annotation = find_latest_completed_annotation(annotations)
        effective_annotation = get_effective_annotation(annotations)
        auto_annotated = is_auto_annotated_assembly(sequencing_task)
        first_annotation = min(annotations, key=lambda item: (item.created_at, item.id)) if annotations else None
        most_recent = latest_annotation.updated_at if latest_annotation and latest_annotation.updated_at > sequencing_task.updated_at else sequencing_task.updated_at
        annotation_started = bool(first_annotation) or auto_annotated

        if auto_annotated:
            top_pipeline = pipeline_label(sequencing_task.task_type)
            top_status = sequencing_task.status
        elif annotation_started and effective_annotation:
            top_pipeline = 'Annotation'
            top_status = effective_annotation.status
        else:
            top_pipeline = pipeline_label(sequencing_task.task_type)
            top_status = sequencing_task.status

        has_auto_json = bool(auto_annotated and sequencing_task.status == 'completed' and sequencing_task.external_job_id)

        rows.append({
            'kind': 'sequencing',
            'process_name': sequencing_task.process_name,
            'pipeline_type': pipeline_label(sequencing_task.task_type),
            'assembly_type_label': pipeline_label(sequencing_task.task_type),
            'status': sequencing_task.status,
            'status_badge': status_badge_class(sequencing_task.status),
            'top_pipeline': top_pipeline,
            'top_status': top_status,
            'top_status_badge': status_badge_class(top_status),
            'sequencing_status': sequencing_task.status,
            'sequencing_status_badge': status_badge_class(sequencing_task.status),
            'input_filename': source_filename(sequencing_task.input_path),
            'updated_at': most_recent,
            'task': sequencing_task,
            'detail_task_id': sequencing_task.id,
            'annotation_display': effective_annotation,
            'annotation_started': annotation_started,
            'annotation_started_at': first_annotation.created_at if first_annotation else None,
            'annotation_progress_status': effective_annotation.status if effective_annotation else 'not_started',
            'has_more_attempts': len(annotations) > 1,
            'extra_attempts_count': max(len(annotations) - 1, 0),
            'can_annotate': sequencing_task.status == 'completed' and not annotations and not auto_annotated,
            'can_retry_annotation': sequencing_task.status == 'completed' and not latest_completed_annotation and bool(latest_annotation and latest_annotation.status == 'failed') and not auto_annotated,
            'has_fasta': sequencing_task.status == 'completed',
            'has_json': bool(latest_completed_annotation) or has_auto_json,
            'annotation_status_badge': status_badge_class(effective_annotation.status) if effective_annotation else None,
            'is_auto_annotated': auto_annotated,
        })

    for _, attempts in standalone_annotations.items():
        sorted_attempts = sorted(attempts, key=lambda item: (item.updated_at, item.id), reverse=True)
        latest = sorted_attempts[0]
        latest_uploaded_fasta = resolve_uploaded_fasta_input_path(latest)
        rows.append({
            'kind': 'annotation',
            'process_name': latest.process_name,
            'pipeline_type': 'Annotation',
            'status': latest.status,
            'status_badge': status_badge_class(latest.status),
            'input_filename': source_filename(latest.input_path),
            'updated_at': latest.updated_at,
            'task': latest,
            'detail_task_id': latest.id,
            'annotation_display': latest,
            'has_more_attempts': len(sorted_attempts) > 1,
            'extra_attempts_count': max(len(sorted_attempts) - 1, 0),
            'can_annotate': False,
            'can_retry_annotation': False,
            'has_fasta': bool(latest_uploaded_fasta),
            'has_json': bool(latest.status == 'completed' and latest.external_job_id),
            'annotation_status_badge': status_badge_class(latest.status),
        })

    for _, attempts in json_tasks.items():
        sorted_attempts = sorted(attempts, key=lambda item: (item.updated_at, item.id), reverse=True)
        latest = sorted_attempts[0]
        rows.append({
            'kind': 'json',
            'process_name': latest.process_name,
            'pipeline_type': 'From JSON',
            'status': latest.status,
            'status_badge': status_badge_class(latest.status),
            'input_filename': source_filename(latest.input_path),
            'updated_at': latest.updated_at,
            'task': latest,
            'detail_task_id': latest.id,
            'annotation_display': None,
            'has_more_attempts': len(sorted_attempts) > 1,
            'extra_attempts_count': max(len(sorted_attempts) - 1, 0),
            'can_annotate': False,
            'can_retry_annotation': False,
            'has_fasta': False,
            'has_json': bool(latest.status == 'completed' and get_json_upload_for_task(latest)),
            'annotation_status_badge': None,
        })

    rows.sort(key=lambda row: (row['updated_at'], row['detail_task_id']), reverse=True)
    return rows


def build_task_context(user, task):
    if task.task_type in ASSEMBLY_TYPES:
        sequencing_task = task
        annotations = list(
            ConversionTask.objects.filter(user=user, previous_task=sequencing_task, task_type='annotation').order_by('-updated_at', '-id')
        )
        latest_annotation = annotations[0] if annotations else None
        return {
            'root_task': sequencing_task,
            'sequencing_task': sequencing_task,
            'latest_annotation_attempt': latest_annotation,
            'latest_completed_annotation_attempt': find_latest_completed_annotation(annotations),
            'latest_annotation_with_uploaded_fasta': find_annotation_with_uploaded_fasta(annotations),
            'latest_json_attempt': None,
            'has_annotation_attempts': bool(annotations),
            'has_json_attempts': False,
            'process_name': sequencing_task.process_name,
            'pipeline_type': pipeline_label(sequencing_task.task_type),
        }

    if task.task_type == 'annotation' and task.previous_task_id:
        sequencing_task = task.previous_task
        annotations = list(
            ConversionTask.objects.filter(user=user, previous_task=sequencing_task, task_type='annotation').order_by('-updated_at', '-id')
        )
        latest_annotation = annotations[0] if annotations else None
        return {
            'root_task': sequencing_task,
            'sequencing_task': sequencing_task,
            'latest_annotation_attempt': latest_annotation,
            'latest_completed_annotation_attempt': find_latest_completed_annotation(annotations),
            'latest_annotation_with_uploaded_fasta': find_annotation_with_uploaded_fasta(annotations),
            'latest_json_attempt': None,
            'has_annotation_attempts': bool(annotations),
            'has_json_attempts': False,
            'process_name': sequencing_task.process_name,
            'pipeline_type': pipeline_label(sequencing_task.task_type),
        }

    if task.task_type == 'annotation':
        annotations = list(
            ConversionTask.objects.filter(
                user=user,
                task_type='annotation',
                previous_task__isnull=True,
                process_name=task.process_name,
                input_path=task.input_path,
            ).order_by('-updated_at', '-id')
        )
        latest_annotation = annotations[0] if annotations else None
        return {
            'root_task': task,
            'sequencing_task': None,
            'latest_annotation_attempt': latest_annotation,
            'latest_completed_annotation_attempt': find_latest_completed_annotation(annotations),
            'latest_annotation_with_uploaded_fasta': find_annotation_with_uploaded_fasta(annotations),
            'latest_json_attempt': None,
            'has_annotation_attempts': bool(annotations),
            'has_json_attempts': False,
            'process_name': task.process_name,
            'pipeline_type': 'Annotation',
        }

    json_attempts = list(
        ConversionTask.objects.filter(
            user=user,
            task_type='from_json',
            process_name=task.process_name,
            input_path=task.input_path,
        ).order_by('-updated_at', '-id')
    )
    latest_json = json_attempts[0] if json_attempts else None
    return {
        'root_task': task,
        'sequencing_task': None,
        'latest_annotation_attempt': None,
        'latest_completed_annotation_attempt': None,
        'latest_annotation_with_uploaded_fasta': None,
        'latest_json_attempt': latest_json,
        'has_annotation_attempts': False,
        'has_json_attempts': bool(json_attempts),
        'process_name': task.process_name,
        'pipeline_type': 'From JSON',
    }


def rename_process_group(user, task, new_name):
    if task.task_type in ASSEMBLY_TYPES:
        ConversionTask.objects.filter(user=user, id=task.id).update(process_name=new_name)
        ConversionTask.objects.filter(user=user, previous_task=task, task_type='annotation').update(process_name=new_name)
        return

    if task.task_type == 'annotation' and task.previous_task_id:
        ConversionTask.objects.filter(user=user, id=task.previous_task_id).update(process_name=new_name)
        ConversionTask.objects.filter(user=user, previous_task_id=task.previous_task_id, task_type='annotation').update(process_name=new_name)
        return

    ConversionTask.objects.filter(
        user=user,
        task_type=task.task_type,
        process_name=task.process_name,
        input_path=task.input_path,
        previous_task__isnull=True,
    ).update(process_name=new_name)


def get_available_fasta_jobs(user):
    """Return completed base assembly jobs that are not already annotated."""
    completed_assembly_tasks = ConversionTask.objects.filter(
        user=user,
        status='completed',
        task_type__in=('sequencing_illumina', 'sequencing_ont'),
        external_job_id__isnull=False,
    ).exclude(external_job_id='').order_by('-updated_at', '-id')

    already_annotated_ids = ConversionTask.objects.filter(
        user=user,
        task_type='annotation',
        status__in=('pending', 'running', 'completed'),
        previous_task__isnull=False,
    ).values_list('previous_task_id', flat=True)

    available_tasks = list(completed_assembly_tasks.exclude(id__in=already_annotated_ids))

    for task in available_tasks:
        resolved_name = resolve_persisted_result_filename(
            user_id=user.id,
            result_prefix='assembly',
            job_id=task.external_job_id,
        )
        task.source_filename = resolved_name or 'Assembly output'
        task.process_name = task.process_name or source_filename(task.input_path)
        task.source_label = format_source_job_label(task)

    return available_tasks


def has_annotation_for_previous(user, previous_task):
    return ConversionTask.objects.filter(
        user=user,
        task_type='annotation',
        status__in=('pending', 'running', 'completed'),
        previous_task=previous_task,
    ).exists()

