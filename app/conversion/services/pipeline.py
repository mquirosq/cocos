import os

from django.db.models import Prefetch
from ..models import ConversionTask, File, ProcessGroup
from .presentation import format_source_job_label
from ..task_types import ANNOTATED_TYPES
from ..tasks import (
    poll_annotation_start,
    poll_assembly_start,
    process_json,
)
from ..utils import upload_file

ASSEMBLY_TYPES = {
    'illumina': ConversionTask.TaskType.ASSEMBLY_ILLUMINA,
    'ont': ConversionTask.TaskType.ASSEMBLY_ONT,
}

def get_assembly_tasks_can_be_annotated(user):
    """Return completed assembly jobs whose FASTA has not been annotated."""

    annotation_tasks = ConversionTask.objects.filter(
        process__user=user,
        task_type=ConversionTask.TaskType.ANNOTATION,
        status__in=(
            ConversionTask.TaskStatus.PENDING,
            ConversionTask.TaskStatus.RUNNING,
            ConversionTask.TaskStatus.COMPLETED,
        ),
    )

    assembly_tasks = (
        ConversionTask.objects
        .filter(
            process__user=user,
            status=ConversionTask.TaskStatus.COMPLETED,
            task_type__in=(
                ConversionTask.TaskType.ASSEMBLY_ILLUMINA,
                ConversionTask.TaskType.ASSEMBLY_ONT,
            ),
        )
        .exclude(output_files__input_conversion_tasks__in=annotation_tasks)
        .select_related('process')
        .prefetch_related(
            Prefetch('output_files',
                queryset=File.objects.filter(file_type=File.FileType.FASTA),
                to_attr='fasta_outputs')
        )
        .order_by('-updated_at', '-id')
    )

    for task in assembly_tasks:
        output_file = task.fasta_outputs[0] if task.fasta_outputs else None

        task.source_filename = (os.path.basename(output_file.file.name) if output_file else 'Assembly output')
        task.source_label = format_source_job_label(task)

    return list(assembly_tasks)


def _has_annotation_for_previous(previous_task):
    """Check if there is an annotation task for the given user and previous assembly task."""
    if not previous_task:
        return False
    return previous_task.process.conversion_tasks.filter(task_type__in=ANNOTATED_TYPES).exists()

# Assembly
def start_assembly(user, assembly_type, fastq, fastq_2=None, annotate=False, complete_version=False):

    if assembly_type not in ASSEMBLY_TYPES:
        raise ValueError("Invalid assembly type.")

    if not fastq:
        raise ValueError("No FASTQ file uploaded.")

    if assembly_type == "illumina" and not fastq_2:
        raise ValueError("Illumina assembly requires a second FASTQ file.")

    if assembly_type == "ont" and fastq_2:
        raise ValueError("Second FASTQ file is only valid for Illumina assembly.")

    file_1 = upload_file(fastq, user=user, file_type=File.FileType.FASTQ)
    file_2 = upload_file(fastq_2, user=user, file_type=File.FileType.FASTQ) if fastq_2 else None

    process = ProcessGroup.objects.create(name=os.path.basename(fastq.name), user=user)
    task = ConversionTask.objects.create(
        external_job_id=None,
        status=ConversionTask.TaskStatus.PENDING,
        task_type=f"assembly_{assembly_type}{'_annotated' if annotate else ''}",
        process = process,
    )

    task.input_files.add(file_1)
    if file_2:
        task.input_files.add(file_2)

    poll_assembly_start.delay(
        task_id=task.id,
        assembly_type=assembly_type,
        annotate=annotate,
        complete_version=complete_version,
    )

    return task


# Annotation
def start_annotation_from_assembly_task(user, source_job_id, complete_version):
    source_task = ConversionTask.objects.filter(
        process__user=user,
        external_job_id=source_job_id,
        status=ConversionTask.TaskStatus.COMPLETED,
        task_type__in=(ConversionTask.TaskType.ASSEMBLY_ILLUMINA, ConversionTask.TaskType.ASSEMBLY_ONT),
    ).first()

    if not source_task:
        raise ValueError('Selected assembly result is not available for annotation.')

    if _has_annotation_for_previous(source_task):
        raise ValueError('This assembly result already has an annotation task.')

    if source_task.process.user != user:
        raise ValueError('You do not have permission to annotate this assembly result.')
    
    if source_task.status != ConversionTask.TaskStatus.COMPLETED:
        raise ValueError('Selected assembly result is not ready for annotation.')

    task = ConversionTask.objects.create(
        status=ConversionTask.TaskStatus.PENDING,
        task_type=ConversionTask.TaskType.ANNOTATION,
        process=source_task.process,
    )
    task.input_files.set(source_task.output_files.all())

    poll_annotation_start.delay(
        task_id=task.id,
        complete_version=complete_version,
    )

    return task

def start_annotation_from_uploaded_fasta(user, fasta, complete_version):
    if not fasta:
        raise ValueError('No FASTA file uploaded for annotation.')
    
    file = upload_file(fasta, user=user, file_type=File.FileType.FASTA)

    process = ProcessGroup.objects.create(name=os.path.basename(file.file.name), user=user)
    task = ConversionTask.objects.create(
        external_job_id=None,
        status=ConversionTask.TaskStatus.PENDING,
        task_type=ConversionTask.TaskType.ANNOTATION,
        process=process
    )

    task.input_files.add(file)

    poll_annotation_start.delay(task_id=task.id, complete_version=complete_version)

    return task

# JSON Parsing
def start_json_processing(user, feature_file, complete_version=False):
    if not feature_file:
        raise ValueError('Select a JSON file.')

    file = upload_file(feature_file, user=user, file_type=File.FileType.JSON)

    process = ProcessGroup.objects.create(name=os.path.basename(file.file.name), user=user)
    task = ConversionTask.objects.create(
        status=ConversionTask.TaskStatus.PENDING,
        task_type=ConversionTask.TaskType.FROM_JSON,
        process=process,
    )

    task.input_files.add(file)

    process_json.delay(task_id=task.id, complete_version=complete_version)

    return task
