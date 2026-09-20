import os
from ..models import ConversionTask, File
from .presentation import format_source_job_label
from ..task_types import ANNOTATED_TYPES

def get_available_fasta_jobs(user):
    """Return completed assembly jobs whose FASTA has not been annotated."""

    completed_assembly_tasks = (ConversionTask.objects.filter(
            process__user=user,
            status=ConversionTask.TaskStatus.COMPLETED,
            task_type__in=(
                ConversionTask.TaskType.ASSEMBLY_ILLUMINA,
                ConversionTask.TaskType.ASSEMBLY_ONT,
            ),
        )
        .select_related('process')
        .prefetch_related('output_files')
        .order_by('-updated_at', '-id')
    )

    annotation_input_files = File.objects.filter(
        input_conversion_tasks__process__user=user,
        input_conversion_tasks__task_type=ConversionTask.TaskType.ANNOTATION,
        input_conversion_tasks__status__in=(
            ConversionTask.TaskStatus.PENDING,
            ConversionTask.TaskStatus.RUNNING,
            ConversionTask.TaskStatus.COMPLETED,
        ),
    )

    available_tasks = list(completed_assembly_tasks.exclude(output_files__in=annotation_input_files))

    for task in available_tasks:
        output_file = task.output_files.filter(file_type=File.FileType.FASTA).first()

        task.source_filename = (os.path.basename(output_file.file.name) if output_file else "Assembly output")
        task.source_label = format_source_job_label(task)

    return available_tasks


def has_annotation_for_previous(previous_task):
    """Check if there is an annotation task for the given user and previous assembly task."""
    if not previous_task:
        return False
    return previous_task.process.conversion_tasks.filter(task_type__in=ANNOTATED_TYPES).exists()