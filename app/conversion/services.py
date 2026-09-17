import os
from .models import ConversionTask, File
from .presentation import format_source_job_label, pipeline_label, status_badge_class
from .task_types import ASSEMBLY_TYPES, ANNOTATED_TYPES, ASSEMBLY_AND_ANNOTATION_TYPES

FASTA_EXTENSIONS = {'.fa', '.fasta', '.fna', '.ffn', '.faa', '.frn'}

def annotation_process_key(task):
    return f"{task.process.name}::{task.input_files.first().file.name if hasattr(task.input_files.first(), 'file') else 'Unnamed Input'}"


def is_auto_annotated_assembly(task):
        return bool(task and task.task_type in ASSEMBLY_AND_ANNOTATION_TYPES)


def find_latest_completed_annotation(annotations):
    for annotation in annotations:
        if annotation.status == ConversionTask.TaskStatus.COMPLETED:
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
        if attempt.input_files.exists() and attempt.input_files.first() and attempt.input_files.first().file_type == File.FileType.FASTA:
            return attempt
    return None


def derive_process_name(task, fallback_name=None):
    if fallback_name:
        return fallback_name
    if task.previous_task_id and task.previous_task and task.previous_task.process.name:
        return task.previous_task.process.name
    if task.process.name:
        return task.process.name
    return (task.input_files.first().file.name if hasattr(task.input_files.first(), 'file') else None) or "Unnamed Process"


def get_json_upload_for_task(task):
    """Return the JSON File object for a task, or None if not found."""

    if task.task_type in ANNOTATED_TYPES:
        if task.output_files.exists():
            return task.output_files.filter(file_type=File.FileType.JSON).first()

    elif task.task_type == ConversionTask.TaskType.FROM_JSON:
        input_file = task.input_files.first()
        return input_file

    return None

def get_fasta_upload_for_task(task):
    """Return the absolute path to the FASTA file for a task, or None if not found."""
    if task.task_type == ConversionTask.TaskType.ANNOTATION:
        return task.input_files.first()

    if task.task_type in ASSEMBLY_TYPES:
        return task.output_files.filter(file_type=File.FileType.FASTA).first()

    return None


def build_process_rows(user):
    tasks = list(ConversionTask.objects.filter(process__user=user).select_related('previous_task').order_by('-updated_at', '-id'))

    assembly_tasks = [task for task in tasks if task.task_type in ASSEMBLY_TYPES]
    assembly_by_id = {task.id: task for task in assembly_tasks}

    annotations_by_parent = {}
    standalone_annotations = {}
    json_tasks = {}

    for task in tasks:
        task.process.name = derive_process_name(task)
        if task.task_type == ConversionTask.TaskType.ANNOTATION and task.previous_task_id in assembly_by_id:
            annotations_by_parent.setdefault(task.previous_task_id, []).append(task)
        elif task.task_type == ConversionTask.TaskType.ANNOTATION and task.previous_task_id is None:
            standalone_annotations.setdefault(annotation_process_key(task), []).append(task)
        elif task.task_type == ConversionTask.TaskType.FROM_JSON:
            json_tasks.setdefault(annotation_process_key(task), []).append(task)

    rows = []

    for assembly_task in assembly_tasks:
        annotations = sorted(annotations_by_parent.get(assembly_task.id, []), key=lambda item: (item.updated_at, item.id), reverse=True)
        latest_annotation = annotations[0] if annotations else None
        latest_completed_annotation = find_latest_completed_annotation(annotations)
        effective_annotation = get_effective_annotation(annotations)
        auto_annotated = is_auto_annotated_assembly(assembly_task)
        first_annotation = min(annotations, key=lambda item: (item.created_at, item.id)) if annotations else None
        most_recent = latest_annotation.updated_at if latest_annotation and latest_annotation.updated_at > assembly_task.updated_at else assembly_task.updated_at
        annotation_started = bool(first_annotation) or auto_annotated

        if auto_annotated:
            top_pipeline = pipeline_label(assembly_task.task_type)
            top_status = assembly_task.status
        elif annotation_started and effective_annotation:
            top_pipeline = 'Annotation'
            top_status = effective_annotation.status
        else:
            top_pipeline = pipeline_label(assembly_task.task_type)
            top_status = assembly_task.status

        has_auto_json = bool(auto_annotated and assembly_task.status == ConversionTask.TaskStatus.COMPLETED and assembly_task.external_job_id)

        rows.append({
            'kind': 'assembly',
            'process_name': assembly_task.process.name,
            'pipeline_type': pipeline_label(assembly_task.task_type),
            'assembly_type_label': pipeline_label(assembly_task.task_type),
            'status': assembly_task.status,
            'status_badge': status_badge_class(assembly_task.status),
            'top_pipeline': top_pipeline,
            'top_status': top_status,
            'top_status_badge': status_badge_class(top_status),
            'assembly_status': assembly_task.status,
            'assembly_status_badge': status_badge_class(assembly_task.status),
            'input_filename': (assembly_task.input_files.first().file.name if hasattr(assembly_task.input_files.first(), 'file') else None),
            'updated_at': most_recent,
            'task': assembly_task,
            'detail_task_id': assembly_task.id,
            'annotation_display': effective_annotation,
            'annotation_started': annotation_started,
            'annotation_started_at': first_annotation.created_at if first_annotation else None,
            'annotation_progress_status': effective_annotation.status if effective_annotation else 'not_started',
            'has_more_attempts': len(annotations) > 1,
            'extra_attempts_count': max(len(annotations) - 1, 0),
            'can_annotate': assembly_task.status == ConversionTask.TaskStatus.COMPLETED and not annotations and not auto_annotated,
            'can_retry_annotation': assembly_task.status == ConversionTask.TaskStatus.COMPLETED and not latest_completed_annotation and bool(latest_annotation and latest_annotation.status == ConversionTask.TaskStatus.FAILED) and not auto_annotated,
            'has_fasta': assembly_task.status == ConversionTask.TaskStatus.COMPLETED,
            'has_json': bool(latest_completed_annotation) or has_auto_json,
            'annotation_status_badge': status_badge_class(effective_annotation.status) if effective_annotation else None,
            'is_auto_annotated': auto_annotated,
        })

    for _, attempts in standalone_annotations.items():
        sorted_attempts = sorted(attempts, key=lambda item: (item.updated_at, item.id), reverse=True)
        latest = sorted_attempts[0]
        latest_uploaded_fasta = latest.input_files.first() if latest.input_files.exists() and latest.input_files.first().file_type == File.FileType.FASTA else None
        rows.append({
            'kind': 'annotation',
            'process_name': latest.process.name,
            'pipeline_type': 'Annotation',
            'status': latest.status,
            'status_badge': status_badge_class(latest.status),
            'input_filename': (latest.input_files.first().file.name if hasattr(latest.input_files.first(), 'file') else None),
            'updated_at': latest.updated_at,
            'task': latest,
            'detail_task_id': latest.id,
            'annotation_display': latest,
            'has_more_attempts': len(sorted_attempts) > 1,
            'extra_attempts_count': max(len(sorted_attempts) - 1, 0),
            'can_annotate': False,
            'can_retry_annotation': False,
            'has_fasta': bool(latest_uploaded_fasta),
            'has_json': bool(latest.status == ConversionTask.TaskStatus.COMPLETED and latest.external_job_id),
            'annotation_status_badge': status_badge_class(latest.status),
        })

    for _, attempts in json_tasks.items():
        sorted_attempts = sorted(attempts, key=lambda item: (item.updated_at, item.id), reverse=True)
        latest = sorted_attempts[0]
        rows.append({
            'kind': 'json',
            'process_name': latest.process.name,
            'pipeline_type': 'From JSON',
            'status': latest.status,
            'status_badge': status_badge_class(latest.status),
            'input_filename': (latest.input_files.first().file.name if hasattr(latest.input_files.first(), 'file') else None),
            'updated_at': latest.updated_at,
            'task': latest,
            'detail_task_id': latest.id,
            'annotation_display': None,
            'has_more_attempts': len(sorted_attempts) > 1,
            'extra_attempts_count': max(len(sorted_attempts) - 1, 0),
            'can_annotate': False,
            'can_retry_annotation': False,
            'has_fasta': False,
            'has_json': bool(latest.status == ConversionTask.TaskStatus.COMPLETED and get_json_upload_for_task(latest)),
            'annotation_status_badge': None,
        })

    rows.sort(key=lambda row: (row['updated_at'], row['detail_task_id']), reverse=True)
    return rows


def build_task_context(user, task):
    if task.task_type in ASSEMBLY_TYPES:
        assembly_task = task
        annotations = list(
            ConversionTask.objects.filter(process__user=user, previous_task=assembly_task, task_type=ConversionTask.TaskType.ANNOTATION).order_by('-updated_at', '-id')
        )
        latest_annotation = annotations[0] if annotations else None
        return {
            'root_task': assembly_task,
            'assembly_task': assembly_task,
            'latest_annotation_attempt': latest_annotation,
            'latest_completed_annotation_attempt': find_latest_completed_annotation(annotations),
            'latest_annotation_with_uploaded_fasta': find_annotation_with_uploaded_fasta(annotations),
            'latest_json_attempt': None,
            'has_annotation_attempts': bool(annotations),
            'has_json_attempts': False,
            'process_name': assembly_task.process.name,
            'pipeline_type': pipeline_label(assembly_task.task_type),
        }

    if task.task_type == ConversionTask.TaskType.ANNOTATION and task.previous_task_id:
        assembly_task = task.previous_task
        annotations = list(
            ConversionTask.objects.filter(process__user=user, previous_task=assembly_task, task_type=ConversionTask.TaskType.ANNOTATION).order_by('-updated_at', '-id')
        )
        latest_annotation = annotations[0] if annotations else None
        return {
            'root_task': assembly_task,
            'assembly_task': assembly_task,
            'latest_annotation_attempt': latest_annotation,
            'latest_completed_annotation_attempt': find_latest_completed_annotation(annotations),
            'latest_annotation_with_uploaded_fasta': find_annotation_with_uploaded_fasta(annotations),
            'latest_json_attempt': None,
            'has_annotation_attempts': bool(annotations),
            'has_json_attempts': False,
            'process_name': assembly_task.process.name,
            'pipeline_type': pipeline_label(assembly_task.task_type),
        }

    if task.task_type == ConversionTask.TaskType.ANNOTATION:
        annotations = list(
            ConversionTask.objects.filter(
                process__user=user,
                task_type=ConversionTask.TaskType.ANNOTATION,
                previous_task__isnull=True,
                process__name=task.process.name,
                input_files=task.input_files.first(),
            ).order_by('-updated_at', '-id')
        )
        latest_annotation = annotations[0] if annotations else None
        return {
            'root_task': task,
            'assembly_task': None,
            'latest_annotation_attempt': latest_annotation,
            'latest_completed_annotation_attempt': find_latest_completed_annotation(annotations),
            'latest_annotation_with_uploaded_fasta': find_annotation_with_uploaded_fasta(annotations),
            'latest_json_attempt': None,
            'has_annotation_attempts': bool(annotations),
            'has_json_attempts': False,
            'process_name': task.process.name,
            'pipeline_type': 'Annotation',
        }

    json_attempts = list(
        ConversionTask.objects.filter(
            process__user=user,
            task_type=ConversionTask.TaskType.FROM_JSON,
            process__name=task.process.name,
            input_files=task.input_files.first(),
        ).order_by('-updated_at', '-id')
    )
    latest_json = json_attempts[0] if json_attempts else None
    return {
        'root_task': task,
        'assembly_task': None,
        'latest_annotation_attempt': None,
        'latest_completed_annotation_attempt': None,
        'latest_annotation_with_uploaded_fasta': None,
        'latest_json_attempt': latest_json,
        'has_annotation_attempts': False,
        'has_json_attempts': bool(json_attempts),
        'process_name': task.process.name,
        'pipeline_type': 'From JSON',
    }


def rename_task_process(user, task, new_name):
    if task.process.user.id != user.id:
        return

    task.process.name = new_name
    task.process.save(update_fields=["name"])


def get_available_fasta_jobs(user):
    """Return completed base assembly jobs that are not already annotated."""
    completed_assembly_tasks = ConversionTask.objects.filter(
        process__user=user,
        status=ConversionTask.TaskStatus.COMPLETED,
        task_type__in=(ConversionTask.TaskType.ASSEMBLY_ILLUMINA, ConversionTask.TaskType.ASSEMBLY_ONT),
        external_job_id__isnull=False,
    ).exclude(external_job_id='').order_by('-updated_at', '-id')

    already_annotated_ids = ConversionTask.objects.filter(
        process__user=user,
        task_type=ConversionTask.TaskType.ANNOTATION,
        status__in=(ConversionTask.TaskStatus.PENDING, ConversionTask.TaskStatus.RUNNING, ConversionTask.TaskStatus.COMPLETED),
        previous_task__isnull=False,
    ).values_list('previous_task_id', flat=True)

    available_tasks = list(completed_assembly_tasks.exclude(id__in=already_annotated_ids))

    for task in available_tasks:
        task.source_filename = (os.path.basename(task.output_files.first().file.name) if task.output_files.first() else "Assembly output")
        task.source_label = format_source_job_label(task)

    return available_tasks


def has_annotation_for_previous(user, previous_task):
    return ConversionTask.objects.filter(
        process__user=user,
        task_type=ConversionTask.TaskType.ANNOTATION,
        status__in=(ConversionTask.TaskStatus.PENDING, ConversionTask.TaskStatus.RUNNING, ConversionTask.TaskStatus.COMPLETED),
        previous_task=previous_task,
    ).exists()

