from .utils import source_filename

def format_source_job_label(task):
    """Format a user-friendly label for a task, using process name or input filename."""
    if task.process_name:
        return task.process_name
    source_name = getattr(task, 'source_filename', None) or source_filename(task.input_path)
    timestamp = task.updated_at.strftime('%Y-%m-%d %H:%M') if task.updated_at else ''
    pieces = [source_name, task.get_task_type_display()]
    if timestamp:
        pieces.append(timestamp)
    return ' · '.join(pieces)


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
        'sequencing_ont_annotated': 'Assembly + Annotation · ONT',
        'sequencing_illumina_annotated': 'Assembly + Annotation · Illumina',
        'sequencing_ont': 'Assembly · ONT',
        'sequencing_illumina': 'Assembly · Illumina',
        'annotation': 'Annotation',
        'from_json': 'From JSON',
    }
    return label_map.get(task_type, 'Process')