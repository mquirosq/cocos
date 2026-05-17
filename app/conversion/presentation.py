from django.contrib.humanize.templatetags.humanize import naturaltime
from .utils import source_filename

def format_source_job_label(task):
    """Format a user-friendly label with process name and relative time."""
    label = task.process_name or source_filename(task.input_path)
    timestamp = task.updated_at or task.created_at
    if timestamp:
        label = f"{label} · {naturaltime(timestamp)}"
    return label


def status_badge_class(status):
    normalized = (status or '').strip().lower().replace('_', ' ')
    return {
        'pending': 'badge-soft badge-warning',
        'running': 'badge-soft badge-info',
        'completed': 'badge-soft badge-success',
        'failed': 'badge-soft badge-error',
    }.get(normalized, 'badge-soft badge-neutral')


def pipeline_label(task_type):
    label_map = {
        'assembly_ont_annotated': 'Assembly + Annotation · ONT',
        'assembly_illumina_annotated': 'Assembly + Annotation · Illumina',
        'assembly_ont': 'Assembly · ONT',
        'assembly_illumina': 'Assembly · Illumina',
        'annotation': 'Annotation',
        'from_json': 'From JSON',
    }
    return label_map.get(task_type, 'Process')