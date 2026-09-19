from django.contrib.humanize.templatetags.humanize import naturaltime

from ..models import ConversionTask

STATUS_BADGE_CLASSES = {
    ConversionTask.TaskStatus.PENDING: 'badge-soft badge-warning',
    ConversionTask.TaskStatus.RUNNING: 'badge-soft badge-info',
    ConversionTask.TaskStatus.COMPLETED: 'badge-soft badge-success',
    ConversionTask.TaskStatus.FAILED: 'badge-soft badge-error',
}

PIPELINE_LABELS = {
    ConversionTask.TaskType.ASSEMBLY_ONT_ANNOTATED: 'Assembly + Annotation · ONT',
    ConversionTask.TaskType.ASSEMBLY_ILLUMINA_ANNOTATED: 'Assembly + Annotation · Illumina',
    ConversionTask.TaskType.ASSEMBLY_ONT: 'Assembly · ONT',
    ConversionTask.TaskType.ASSEMBLY_ILLUMINA: 'Assembly · Illumina',
    ConversionTask.TaskType.ANNOTATION: 'Annotation',
    ConversionTask.TaskType.FROM_JSON: 'From JSON',
    ConversionTask.TaskType.PREDICTION: 'Prediction',
}

def format_source_job_label(task):
    """Format a user-friendly label with process name and relative time."""
    label = task.process.name if task and task.process else "Unnamed Process"
    timestamp = (task.updated_at or task.created_at) if task else None
    if timestamp:
        label = f"{label} · {naturaltime(timestamp)}"
    return label


def status_badge_class(status):
    return STATUS_BADGE_CLASSES.get(status, 'badge-soft badge-neutral')


def pipeline_label(task_type):
    return PIPELINE_LABELS.get(task_type, 'Process')