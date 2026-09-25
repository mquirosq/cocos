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

def build_process_steps(assembly_task=None, annotation=None, json_task=None, is_auto_annotated=False):
    if assembly_task is not None:
        if is_auto_annotated:
            return [
                {
                    "label": "Started",
                    "state": "complete",
                },
                {
                    "label": "Assembling",
                    "state": _task_step_state(assembly_task),
                },
                {
                    "label": "Annotated",
                    "state": _task_step_state(assembly_task),
                },
            ]

        steps = [
            {
                "label": "Started",
                "state": "complete",
            },
            {
                "label": "Assembling",
                "state": _task_step_state(assembly_task),
            },
        ]

        steps.append(
                {
                    "label": "Annotated",
                    "state": _task_step_state(annotation) if annotation is not None else "pending",
                }
            )

        return steps

    if annotation is not None:
        return [
            {
                "label": "Started",
                "state": "complete",
            },
            {
                "label": "Annotating",
                "state": _task_step_state(annotation),
            },
            {
                "label": "Parsed",
                "state": _task_step_state(annotation),
            },
        ]

    if json_task is not None:
        return [
            {
                "label": "Started",
                "state": "complete",
            },
            {
                "label": "Parsed",
                "state": _task_step_state(json_task),
            },
        ]

    return []

def _task_step_state(task):
    if task.status == ConversionTask.TaskStatus.COMPLETED:
        return "complete"

    if task.status == ConversionTask.TaskStatus.FAILED:
        return "error"

    return "current"