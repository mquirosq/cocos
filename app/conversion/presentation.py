from django.contrib.humanize.templatetags.humanize import naturaltime

from .models import ConversionTask
from .utils import source_filename

STATUS_BADGE_CLASSES = {
    ConversionTask.TaskStatus.PENDING: 'badge-soft badge-warning',
    ConversionTask.TaskStatus.RUNNING: 'badge-soft badge-info',
    ConversionTask.TaskStatus.COMPLETED: 'badge-soft badge-success',
    ConversionTask.TaskStatus.FAILED: 'badge-soft badge-error',
}

def format_source_job_label(task):
    """Format a user-friendly label with process name and relative time."""
    label = task.process_name or source_filename(task.input_file.first().file.name if hasattr(task.input_file.first(), 'file') else None) or "Unnamed Process"
    timestamp = task.updated_at or task.created_at
    if timestamp:
        label = f"{label} · {naturaltime(timestamp)}"
    return label


def status_badge_class(status):
    return STATUS_BADGE_CLASSES.get(status, 'badge-soft badge-neutral')


def pipeline_label(task_type):
    label_map = {
        'assembly_ont_annotated': 'Assembly + Annotation · ONT',
        'assembly_illumina_annotated': 'Assembly + Annotation · Illumina',
        'assembly_ont': 'Assembly · ONT',
        'assembly_illumina': 'Assembly · Illumina',
        'annotation': 'Annotation',
        'from_json': 'From JSON',
        'prediction': 'Prediction',
    }
    return label_map.get(task_type, 'Process')