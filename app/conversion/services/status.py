import os
from django.db.models import Max, Prefetch

from ..models import ConversionTask, File, ProcessGroup
from .presentation import pipeline_label, status_badge_class, build_process_steps
from ..task_types import ASSEMBLY_TYPES, ANNOTATED_TYPES, ASSEMBLY_AND_ANNOTATION_TYPES

def get_processes_of_user_prefetch_tasks_and_files(user):
    """
    Return a queryset of ProcessGroup objects for the given user, 
    with prefetching of related ConversionTask objects and related File objects.
    The queryset is ordered by the last updated time of the tasks in descending order.
    """
    return (
        ProcessGroup.objects.filter(user=user)
        .annotate(last_updated=Max('conversion_tasks__updated_at'))
        .prefetch_related(
            Prefetch('conversion_tasks',
                queryset=(
                    ConversionTask.objects
                    .prefetch_related(
                        Prefetch('input_files', to_attr='prefetched_input_files'),
                        Prefetch('output_files', to_attr='prefetched_output_files'),
                    )
                    .order_by('-updated_at', '-id')
                ),
                to_attr='list_tasks',
            )
        )
        .order_by('-last_updated', '-id')
    )

def is_auto_annotated_assembly(task):
    return bool(task and task.task_type in ASSEMBLY_AND_ANNOTATION_TYPES)

def find_latest_completed_annotation(annotations):
    for annotation in annotations:
        if annotation.status == ConversionTask.TaskStatus.COMPLETED:
            return annotation
    return None

def find_annotation_with_uploaded_fasta(annotation_attempts):
    """Return the first annotation attempt that has a valid uploaded FASTA path."""
    for attempt in annotation_attempts:
        if attempt.input_files.exists() and attempt.input_files.first() and attempt.input_files.first().file_type == File.FileType.FASTA:
            return attempt
    return None

def get_prefetched_file(files, file_type):
    return next((file for file in files if file.file_type == file_type), None)

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
    """
    Build a list of process rows for the given user, each containing relevant 
    information about the process and its tasks reasy for the task list view.
    """
    processes = get_processes_of_user_prefetch_tasks_and_files(user)
    rows = []

    for process in processes:
        tasks = process.list_tasks

        assembly_tasks = [task for task in tasks if task.task_type in ASSEMBLY_TYPES]

        annotations = [task for task in tasks if task.task_type == ConversionTask.TaskType.ANNOTATION]

        json_tasks = [task for task in tasks if task.task_type == ConversionTask.TaskType.FROM_JSON]

        if assembly_tasks:
            rows.append(_build_assembly_row(process, assembly_tasks, annotations))
            
        elif annotations:
            rows.append(_build_annotation_row(process, annotations))
                
        elif json_tasks:
            rows.append(_build_json_row(process, json_tasks))

    rows.sort(
        key=lambda row: (row['updated_at'], row['task'].id),
        reverse=True,
    )

    return rows

def _build_assembly_row(process, assembly_tasks, annotations):
    """Build a process row for an assembly task."""

    assembly_task = assembly_tasks[0]
    latest_annotation = annotations[0] if annotations else None
    
    auto_annotated = is_auto_annotated_assembly(assembly_task)
    annotation_started = bool(latest_annotation) or auto_annotated
    
    if latest_annotation:
        top_pipeline = 'Annotation'
        top_status = latest_annotation.status
    else:
        top_pipeline = pipeline_label(assembly_task.task_type)
        top_status = assembly_task.status
    
    most_recent = latest_annotation.updated_at if latest_annotation else assembly_task.updated_at
    
    assembly_completed = assembly_task.status == ConversionTask.TaskStatus.COMPLETED
    
    has_auto_json = auto_annotated and assembly_completed
    
    input_filenames = [
        os.path.basename(file.file.name)
        for file in assembly_task.prefetched_input_files
        if file.file_type == File.FileType.FASTQ
    ]
    
    input_filename = ", ".join(input_filenames)
    
    can_annotate = assembly_completed and not annotations and not auto_annotated
    can_retry_annotation = (latest_annotation.status == ConversionTask.TaskStatus.FAILED if latest_annotation else False) and not auto_annotated
    has_fasta = assembly_completed and get_prefetched_file(assembly_task.prefetched_output_files, File.FileType.FASTA) is not None
    has_json = (latest_annotation.status == ConversionTask.TaskStatus.COMPLETED if latest_annotation else False) or has_auto_json

    stage_class = stage_class = ("process-stage-max" if has_json else "process-stage-mid" if annotation_started else "process-stage-light")
    
    return {
        'kind': 'assembly',
        'process_name': process.name,
        'pipeline_type': pipeline_label(assembly_task.task_type),
        'status': top_status,
        'status_badge': status_badge_class(top_status),
        'top_pipeline': top_pipeline,
        'input_filename': input_filename,
        'updated_at': most_recent,
        'task': assembly_task,
        'annotation_started': annotation_started,
        'can_annotate': can_annotate,
        'can_retry_annotation': can_retry_annotation,
        'has_fasta': has_fasta,
        'has_json': has_json,
        'is_auto_annotated': auto_annotated,
        'steps': build_process_steps(assembly_task=assembly_task, annotation=latest_annotation, is_auto_annotated=auto_annotated),
        'stage_class': stage_class,
    }

def _build_annotation_row(process, annotations):
    """Build a process row for an annotation task."""

    latest = annotations[0]
    latest_uploaded_fasta = get_prefetched_file(latest.prefetched_input_files, File.FileType.FASTA)
    latest_uploaded_json = get_prefetched_file(latest.prefetched_output_files, File.FileType.JSON)

    stage_class = ("process-stage-max" if latest.status == ConversionTask.TaskStatus.COMPLETED else "process-stage-mid")

    return {
        'kind': 'annotation',
        'process_name': process.name,
        'pipeline_type': pipeline_label(latest.task_type),
        'status': latest.status,
        'status_badge': status_badge_class(latest.status),
        'input_filename': os.path.basename(latest_uploaded_fasta.file.name),
        'updated_at': latest.updated_at,
        'task': latest,
        'can_annotate': False,
        'can_retry_annotation': False,
        'has_fasta': bool(latest_uploaded_fasta),
        'has_json': bool(latest_uploaded_json),
        'steps': build_process_steps(annotation=latest),
        'stage_class': stage_class,
    }

def _build_json_row(process, json_tasks):
    """Build a process row for a JSON task."""

    latest = json_tasks[0]
    json_upload = get_prefetched_file(latest.prefetched_input_files, File.FileType.JSON)

    stage_class = ("process-stage-max" if latest.status == ConversionTask.TaskStatus.COMPLETED else "process-stage-dark")

    return {
        'kind': 'json',
        'process_name': process.name,
        'pipeline_type': pipeline_label(latest.task_type),
        'status': latest.status,
        'status_badge': status_badge_class(latest.status),
        'input_filename': os.path.basename(json_upload.file.name),
        'updated_at': latest.updated_at,
        'task': latest,
        'can_annotate': False,
        'can_retry_annotation': False,
        'has_fasta': False,
        'has_json': bool(json_upload),
        'steps': build_process_steps(json_task=latest),
        'stage_class': stage_class,
    }


def build_process_status_context(process):
    """Build the context for the process status template."""

    process_tasks = list(process.conversion_tasks
        .prefetch_related(
            Prefetch('input_files', to_attr='prefetched_input_files'),
            Prefetch('output_files', to_attr='prefetched_output_files'),
        )
        .order_by('-updated_at', '-id')
    )

    assembly_tasks = [task for task in process_tasks if task.task_type in ASSEMBLY_TYPES]
    annotation_tasks = [task for task in process_tasks if task.task_type == ConversionTask.TaskType.ANNOTATION]
    json_tasks = [task for task in process_tasks if task.task_type == ConversionTask.TaskType.FROM_JSON]

    assembly_task = assembly_tasks[0] if assembly_tasks else None
    latest_annotation = annotation_tasks[0] if annotation_tasks else None
    latest_annotation_has_json = bool(get_prefetched_file(latest_annotation.prefetched_output_files, File.FileType.JSON) if latest_annotation else None)

    latest_json = json_tasks[0] if json_tasks else None

    is_auto_annotated = is_auto_annotated_assembly(assembly_task)

    has_completed_assembly = (assembly_task is not None and assembly_task.status == ConversionTask.TaskStatus.COMPLETED)

    can_annotate = (has_completed_assembly and not annotation_tasks and not is_auto_annotated)

    can_retry_annotation = (has_completed_assembly and latest_annotation is not None
        and latest_annotation.status == ConversionTask.TaskStatus.FAILED and not is_auto_annotated)

    # FASTA download
    if has_completed_assembly:
        fasta_download_task_id = assembly_task.id
    elif annotation_tasks:
        fasta_download_task_id = latest_annotation.id
    else:
        fasta_download_task_id = None

    # JSON download
    if latest_annotation_has_json:
        json_download_task_id = latest_annotation.id
    elif is_auto_annotated and has_completed_assembly:
        json_download_task_id = assembly_task.id
    elif (
        latest_json
        and latest_json.status == ConversionTask.TaskStatus.COMPLETED
        and get_prefetched_file(
            latest_json.prefetched_output_files,
            File.FileType.JSON,
        )
    ):
        json_download_task_id = latest_json.id

    else:
        json_download_task_id = None

    process_kind = ('assembly' if assembly_task else 'json' if json_tasks else 'annotation')

    pipeline_badges = []
    if assembly_task:
        pipeline_badges.append(pipeline_label(assembly_task.task_type))
    if latest_annotation:
        pipeline_badges.append(pipeline_label(latest_annotation.task_type))
    if latest_json:
        pipeline_badges.append(pipeline_label(latest_json.task_type))

    latest_task = process_tasks[0]
    latest_task_status = latest_task.status if latest_task else None

    timeline = [_build_timeline_entry(task) for task in reversed(process_tasks)]

    status_badge = status_badge_class(latest_task_status) if latest_task_status else None

    return {
        'first_task': process_tasks[-1], # TODO: Should be removed when the views are refactored to use process_id instead of task_id
        'process_name': process.name,
        'process_kind': process_kind,
        'pipeline_badges': pipeline_badges,
        'latest_task_status': latest_task_status,
        'status_badge': status_badge,
        'last_updated': process_tasks[0].updated_at,
        'created_at': process_tasks[-1].created_at,
        'fasta_download_task_id': fasta_download_task_id,
        'json_download_task_id': json_download_task_id,
        'can_annotate': can_annotate,
        'can_retry_annotation': can_retry_annotation,
        'timeline': timeline,
    }

def _build_timeline_entry(task):
    """Build a timeline entry representing a conversion task."""

    input_filename = None

    for file in task.prefetched_input_files:
        if file.file_type in (File.FileType.FASTQ, File.FileType.FASTA, File.FileType.JSON):
            input_filename = os.path.basename(file.file.name)
            break

    return {
        'label': pipeline_label(task.task_type),
        'status': task.status,
        'status_badge': status_badge_class(task.status),
        'updated_at': task.updated_at,
        'input_filename': input_filename,
    }


def rename_task_process(user, task, new_name):
    if task.process.user.id != user.id:
        return

    task.process.name = new_name
    task.process.save(update_fields=["name"])

