import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app.utils.pagination import get_pagination_page_range
from ..models import ConversionTask, ProcessGroup
from ..services.status import (
    build_process_rows,
    build_process_status_context,
    get_json_upload_for_task,
    is_auto_annotated_assembly,
    rename_task_process,
    get_fasta_upload_for_task,
)
from ..services.status import status_badge_class, pipeline_label
from ..utils import get_current_user_tasks


@login_required
def task_list_view(request):
    """Render process task rows for assembly, annotation, and JSON."""
    rows = build_process_rows(request.user)
    paginator = Paginator(rows, 3)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    return render(request, 'conversion/task_list.html', {
        'page_obj': page_obj,
        'pagination_page_range': get_pagination_page_range(paginator, page_obj.number),
        'pagination_url': reverse('conversion:task_list'),
        'pagination_query': '',
        'pagination_label': 'Processes',
        'pagination_link_attribute': 'data-process-page',
    })

@login_required
def process_status_view(request, process_id):
    process = ProcessGroup.objects.filter(id=process_id).first()
    task = process.conversion_tasks.first() if process else None

    if task.process.user != request.user:
        messages.error(request, 'You do not have permission to view this task.')
        return redirect('conversion:task_list')

    if not task:
        messages.error(request, 'Task not found.')
        return redirect('conversion:task_list')

    context = build_process_status_context(request.user, task)
    assembly_task = context['assembly_task']
    auto_annotated = is_auto_annotated_assembly(assembly_task)
    latest_annotation = context['latest_annotation_attempt']
    latest_json = context['latest_json_attempt']
    latest_completed = context['latest_completed_annotation_attempt']
    latest_step = latest_annotation or latest_json
    latest_step_label = (
        'Annotation' if latest_annotation else ('From JSON' if latest_json else None)
    )


    has_completed_assembly = bool(assembly_task and assembly_task.status == ConversionTask.TaskStatus.COMPLETED)
    can_annotate = has_completed_assembly and not context['has_annotation_attempts'] and not auto_annotated
    can_retry = has_completed_assembly and latest_annotation and latest_annotation.status == ConversionTask.TaskStatus.FAILED and not auto_annotated

    # FASTA download
    fasta_download_task_id = (
        assembly_task.id if has_completed_assembly else
        (context['latest_annotation_with_uploaded_fasta'].id if context['latest_annotation_with_uploaded_fasta'] else None)
    )

    # JSON download
    json_download_task_id = (
        latest_completed.id if latest_completed else
        (latest_json.id if latest_json and latest_json.status == ConversionTask.TaskStatus.COMPLETED and get_json_upload_for_task(latest_json) else None)
        if not latest_completed else None
    )
    if not json_download_task_id and auto_annotated and has_completed_assembly:
        json_download_task_id = assembly_task.id

    process_kind = (
        'assembly' if assembly_task else
        ('json' if context['has_json_attempts'] else 'annotation')
    )

    pipeline_badges = []
    if assembly_task:
        pipeline_badges.append(pipeline_label(assembly_task.task_type))
    if latest_annotation:
        pipeline_badges.append('Annotation')
    elif latest_json:
        pipeline_badges.append('From JSON')

    latest_task = latest_step if latest_step else (assembly_task if assembly_task else task)
    latest_task_status = latest_task.status if latest_task else task.status

    return render(request, 'conversion/process_status.html', {
        'task': task,
        'process_name': context['process_name'],
        'pipeline_badges': pipeline_badges,
        'assembly_task': assembly_task,
        'latest_step': latest_step,
        'latest_step_label': latest_step_label,
        'assembly_input_filename': os.path.basename(assembly_task.input_files.first().file.name) if assembly_task else None,
        'fasta_download_task_id': fasta_download_task_id,
        'json_download_task_id': json_download_task_id,
        'can_annotate': can_annotate,
        'can_retry_annotation': can_retry,
        'status_badge': status_badge_class(latest_task_status),
        'latest_task_status': latest_task_status,
        'assembly_status_badge': status_badge_class(assembly_task.status) if assembly_task else None,
        'latest_step_status_badge': status_badge_class(latest_step.status) if latest_step else None,
        'auto_annotated_assembly': auto_annotated,
        'process_kind': process_kind,    })

@login_required
def download_json_view(request, task_id):
    task = get_object_or_404(get_current_user_tasks(request), id=task_id)

    if task.status != ConversionTask.TaskStatus.COMPLETED:
        return redirect('conversion:process_status', process_id=task.process.id)

    upload = get_json_upload_for_task(task)

    if not upload:
        messages.error(request, 'JSON file is not available for download.')
        return redirect('conversion:process_status', process_id=task.process.id)

    try:
        file = upload.file.open('rb')
        filename = os.path.basename(upload.file.name)

        response = FileResponse(
            file,
            as_attachment=True,
            filename=filename,
            content_type='application/json',
        )
        return response

    except Exception:
        messages.error(request,'Could not read the JSON file. Please try again later.')
        return redirect('conversion:process_status', process_id=task.process.id)

@login_required
def download_fasta_view(request, task_id):
    task = get_object_or_404(get_current_user_tasks(request), id=task_id)

    if task.status != ConversionTask.TaskStatus.COMPLETED:
        return redirect('conversion:process_status', process_id=task.process.id)

    upload = get_fasta_upload_for_task(task)

    if not upload:
        messages.error(request, 'FASTA file is not available for download.')
        return redirect('conversion:process_status', process_id=task.process.id)

    try:
        file = upload.file.open('rb')
        filename = os.path.basename(upload.file.name)

        response = FileResponse(
            file,
            as_attachment=True,
            filename=filename,
            content_type='application/octet-stream',
        )
        return response

    except Exception:
        messages.error(request, 'Could not read the FASTA file. Please try again later.')
        return redirect('conversion:process_status', process_id=task.process.id)
    
@require_POST
@login_required
def rename_process_view(request, task_id):
    task = get_object_or_404(get_current_user_tasks(request), id=task_id)
    new_name = (request.POST.get('process_name') or '').strip()
    if not new_name:
        messages.error(request, 'Process name cannot be empty.')
        return redirect('conversion:process_status', process_id=task.process.id)

    rename_task_process(request.user, task, new_name)
    messages.success(request, 'Process name updated.')
    return redirect('conversion:process_status', process_id=task.process.id)
