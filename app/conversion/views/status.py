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
    get_fasta_upload_for_task,
    get_json_upload_for_task,
    rename_task_process,
)
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

    if not process:
        messages.error(request, 'Process not found.')
        return redirect('conversion:task_list')

    if process.user != request.user:
        messages.error(request, 'You do not have permission to view this process.')
        return redirect('conversion:task_list')

    context = build_process_status_context(process)

    return render(request, 'conversion/process_status.html', context)


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
