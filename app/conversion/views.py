import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ConversionTask
from .parsers import parse_file
from .services import (
    build_process_rows,
    build_task_context,
    get_available_fasta_jobs,
    get_json_upload_for_task,
    has_annotation_for_previous,
    is_auto_annotated_assembly,
    rename_process_group,
    get_fasta_upload_for_task,
)
from .presentation import format_source_job_label, status_badge_class
from .tasks import (
    poll_annotation_from_assembly_start,
    poll_annotation_start,
    poll_assembly_start,
)
from .utils import (
    source_filename,
    upload_file,
)

def _get_current_user_tasks(request):
    """Return tasks filtered by authenticated user."""
    return ConversionTask.objects.filter(user=request.user)


def _annotation_context(request, active_tab='fasta', **extra):
    context = {
        'active_tab': active_tab,
        'available_fasta_jobs': get_available_fasta_jobs(request.user),
    }
    context.update(extra)
    return context


def _start_annotation_from_source_job(request, source_job_id):
    available_jobs = get_available_fasta_jobs(request.user)
    previous_task = next((task for task in available_jobs if task.external_job_id == source_job_id), None)
    
    if not previous_task:
        messages.error(request, 'Selected FASTA is not available for annotation.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    if has_annotation_for_previous(request.user, previous_task):
        messages.error(request, 'This FASTA output already has an annotation task.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    if previous_task.user != request.user:
        messages.error(request, 'You do not have permission to annotate this FASTA output.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))
    
    if previous_task.status != 'completed':
        messages.error(request, 'Selected FASTA output is not ready for annotation.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    task = ConversionTask.objects.create(
        external_job_id=None,
        status='pending',
        input_path=previous_task.input_path,
        task_type='annotation',
        user=request.user,
        previous_task=previous_task,
        process_name=previous_task.process_name or format_source_job_label(previous_task),
    )

    poll_annotation_from_assembly_start.delay(
        job_id=source_job_id,
        user_id=request.user.id,
        new_task_id=task.id,
        complete_version=request.POST.get('complete') == 'on',
    )

    message = f"Annotation task started from previous assembly job {source_job_id}. You will be notified when it's complete."
    messages.info(request, message)
    return redirect('conversion:task_status', task_id=task.id)


def _start_annotation_from_uploaded_fasta(request, fasta):
    if not fasta:
        messages.error(request, 'Select a previous FASTA output or upload a FASTA file.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    fasta_bytes = fasta.read()
    dest_path = upload_file(
        fasta,
        user_id=request.user.id,
        file_kind='fasta',
        persistent=True,
    )

    task = ConversionTask.objects.create(
        external_job_id=None,
        status='pending',
        input_path=dest_path,
        task_type='annotation',
        user=request.user,
        previous_task=None,
        process_name=source_filename(dest_path),
    )

    poll_annotation_start.delay(
        fasta_bytes=fasta_bytes,
        dest_path=dest_path,
        task_id=task.id,   
        complete_version=request.POST.get('complete') == 'on',
    )

    message = f"Annotation task started for file {fasta.name}. You will be notified when it's complete."
    messages.info(request, message)
    return redirect('conversion:task_status', task_id=task.id)

@login_required
def assembly_ui(request):
    """Render Assembly workflow page (FASTQ to FASTA)."""
    return render(request, 'conversion/assembly.html')


@login_required
def annotation_ui(request):
    """Render Annotation workflow page with FASTA and JSON tabs."""
    return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

@require_POST
@login_required
def annotation_task(request):
    """
    Allow users to upload a FASTA file via a simple web form to start an external annotation task.
    On submission, create an AnnotationTask and trigger polling of its status.
    """
    source_job_id = (request.POST.get('source_job_id') or '').strip()
    fasta = request.FILES.get('fasta_file')

    if source_job_id:
        return _start_annotation_from_source_job(request, source_job_id)
    else:
        return _start_annotation_from_uploaded_fasta(request, fasta)

@require_POST
@login_required
def assembly_task(request):
    """
    Allow users to upload a FASTQ file via a simple web form to start an external assembly task.
    On submission, create a ConversionTask and trigger polling of its status.
    """
    print("Received assembly task request")
    assembly_type = request.POST.get('assembly_type') or request.POST.get('assembly_type')
    annotate = request.POST.get('annotate') == 'on'  # Checkbox value

    fastq = request.FILES.get('fastq_file')
    if not fastq:
        messages.error(request, 'No FASTQ file uploaded.')
        return redirect('conversion:assembly_ui')

    fastq_2 = request.FILES.get('fastq_file_2')  # For Illumina
    if assembly_type != 'illumina' and fastq_2:
        messages.error(request, 'Second FASTQ file is only valid for Illumina assembly.')
        return redirect('conversion:assembly_ui')

    dest_path = upload_file(
        fastq,
        user_id=request.user.id,
        file_kind='fastq',
        persistent=False,
    )
    dest_path_2 = None
    if fastq_2:
        dest_path_2 = upload_file(
            fastq_2,
            user_id=request.user.id,
            file_kind='fastq',
            persistent=False,
        )

    task = ConversionTask.objects.create(
        external_job_id=None,
        status='pending',
        input_path=dest_path + ("," + dest_path_2 if dest_path_2 else ""),
        task_type=f"assembly_{assembly_type}{'_annotated' if annotate else ''}",
        user=request.user,
        process_name=fastq.name,
    )

    print(f"Starting assembly task with type {assembly_type} for file {fastq.name}")
    poll_assembly_start.delay(
        assembly_type=assembly_type,
        dest_path=dest_path,
        dest_path_2=dest_path_2,
        annotate=annotate,
        task_id=task.id,
        complete_version=request.POST.get('complete') == 'on',
    )

    message = f"Assembly task started for file {fastq.name}. You will be notified when it's complete."
    messages.info(request, message)

    return redirect('conversion:assembly_ui')
    
@require_POST
@login_required
def annotation_from_assembly_task(request, job_id):
    """
    Start an annotation task based on the result of a previous assembly task.
    Expects a job_id from the assembly task to be provided in the POST data.
    """
    if not job_id:
        messages.error(request, 'No assembly job id was provided for annotation.')
        return redirect('conversion:annotation_ui')

    print(f"Starting annotation task from assembly job with ID: {job_id}")

    previous_task = _get_current_user_tasks(request).filter(
        external_job_id=job_id,
        status='completed',
        task_type__in=('assembly_illumina', 'assembly_ont'),
    ).first()
    if not previous_task:
        messages.error(request, 'Assembly job not found or not available for annotation.')
        return redirect('conversion:annotation_ui')

    if has_annotation_for_previous(request.user, previous_task):
        messages.warning(request, 'This assembly result already has an annotation task.')
        return redirect('conversion:annotation_ui')
    
    if previous_task.user != request.user:
        messages.error(request, 'You do not have permission to annotate this assembly result.')
        return redirect('conversion:annotation_ui')
    
    if previous_task.status != 'completed':
        messages.error(request, 'Selected assembly job is not ready for annotation.')
        return redirect('conversion:annotation_ui')

    task = ConversionTask.objects.create(
        external_job_id=None,
        status='pending',
        input_path=previous_task.input_path,
        task_type='annotation',
        user=request.user,
        previous_task=previous_task,
        process_name=previous_task.process_name,
    )

    poll_annotation_from_assembly_start.delay(
        user_id=request.user.id,
        job_id=job_id,
        new_task_id=task.id,
        complete_version=request.POST.get('complete') == 'on',
    )

    message = f"Annotation task started for assembly job {job_id}. You will be notified when it's complete."
    messages.info(request, message)
    return redirect('conversion:task_status', task_id=task.id)

@login_required
def parse_feature_file(request):
    """Handle Bakta JSON parsing from Annotation tab."""
    if request.method == 'POST':
        feature_file = request.FILES.get('feature_file')
        if not feature_file:
            messages.error(request, 'Select a JSON file.')
            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))

        task = ConversionTask.objects.create(
            external_job_id=None,
            status='pending',
            input_path=feature_file.name,
            task_type='from_json',
            user=request.user,
            process_name=source_filename(feature_file.name),
        )

        complete_version = request.POST.get('complete') == 'on'
        try:
            data = json.load(feature_file)
            feature_file.seek(0)
        except Exception:
            task.status = 'failed'
            task.save(update_fields=['status', 'updated_at'])
            messages.error(request, 'Error decoding JSON file.')
            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))
        
        try:
            file_upload = parse_file(
                "bakta_json",
                data,
                feature_file,
                user=request.user,
                options={"complete_version": complete_version}
            )
        except Exception as e:
            task.status = 'failed'
            task.save(update_fields=['status', 'updated_at'])
            messages.error(request, f'Error parsing features: {e}')
            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))

        task.status = 'completed'
        task.input_path = file_upload.file.name
        task.save(update_fields=['status', 'input_path', 'updated_at'])

        messages.success(request, 'File parsed successfully!')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json', file_upload=file_upload))
    return redirect('conversion:annotation_ui')

# Tasks
@login_required
def task_list_view(request):
    """Render process task rows for assembly, annotation, and JSON."""
    rows = build_process_rows(request.user)
    paginator = Paginator(rows, 3)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'conversion/task_list.html', {
        'page_obj': page_obj,
    })

@login_required
def task_status_view(request, task_id):
    task = get_object_or_404(_get_current_user_tasks(request), id=task_id)

    if task.user != request.user:
        messages.error(request, 'You do not have permission to view this task.')
        return redirect('conversion:task_list')

    context = build_task_context(request.user, task)
    assembly_task = context['assembly_task']
    auto_annotated = is_auto_annotated_assembly(assembly_task)
    latest_annotation = context['latest_annotation_attempt']
    latest_json = context['latest_json_attempt']
    latest_completed = context['latest_completed_annotation_attempt']
    latest_step = latest_annotation or latest_json
    latest_step_label = (
        'Annotation' if latest_annotation else ('From JSON' if latest_json else None)
    )

    has_completed_assembly = bool(assembly_task and assembly_task.status == 'completed')
    can_annotate = has_completed_assembly and not context['has_annotation_attempts'] and not auto_annotated
    can_retry = has_completed_assembly and latest_annotation and latest_annotation.status == 'failed' and not auto_annotated

    # FASTA download
    fasta_download_task_id = (
        assembly_task.id if has_completed_assembly else
        (context['latest_annotation_with_uploaded_fasta'].id if context['latest_annotation_with_uploaded_fasta'] else None)
    )

    # JSON download
    json_download_task_id = (
        latest_completed.id if latest_completed else
        (latest_json.id if latest_json and latest_json.status == 'completed' and get_json_upload_for_task(latest_json) else None)
        if not latest_completed else None
    )
    if not json_download_task_id and auto_annotated and has_completed_assembly:
        json_download_task_id = assembly_task.id

    process_kind = (
        'assembly' if assembly_task else
        ('json' if context['has_json_attempts'] else 'annotation')
    )

    return render(request, 'conversion/task_status.html', {
        'task': task,
        'process_name': context['process_name'],
        'pipeline_type': context['pipeline_type'],
        'assembly_task': assembly_task,
        'latest_step': latest_step,
        'latest_step_label': latest_step_label,
        'assembly_input_filename': source_filename(assembly_task.input_path) if assembly_task else None,
        'fasta_download_task_id': fasta_download_task_id,
        'json_download_task_id': json_download_task_id,
        'can_annotate': can_annotate,
        'can_retry_annotation': can_retry,
        'status_badge': status_badge_class(task.status),
        'assembly_status_badge': status_badge_class(assembly_task.status) if assembly_task else None,
        'latest_step_status_badge': status_badge_class(latest_step.status) if latest_step else None,
        'auto_annotated_assembly': auto_annotated,
        'process_kind': process_kind,
    })

@login_required
def download_json_view(request, task_id):
    """
    Download the Bakta JSON result for a completed task as an attachment.
    """
    task = get_object_or_404(_get_current_user_tasks(request), id=task_id)
    if task.status != 'completed':
        return redirect('conversion:task_status', task_id=task.id)

    upload = get_json_upload_for_task(task)
    if not upload:
        messages.error(request, 'JSON file is not available for download.')
        return redirect('conversion:task_status', task_id=task.id)

    try:
        if hasattr(upload, 'file'):
            upload.file.open('rb')
            content = upload.file.read()
            upload.file.close()
            filename = os.path.basename(upload.file.name)
        elif isinstance(upload, str) and os.path.exists(upload):
            with open(upload, 'rb') as f:
                content = f.read()
            filename = os.path.basename(upload)
        else:
            raise ValueError('Invalid upload reference')
    except Exception:
        messages.error(request, 'Could not read the JSON file. Please try again later.')
        return redirect('conversion:task_status', task_id=task.id)

    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def download_fasta_view(request, task_id):
    task = get_object_or_404(_get_current_user_tasks(request), id=task_id)
    if task.status != 'completed':
        return redirect('conversion:task_status', task_id=task.id)

    fasta_path = get_fasta_upload_for_task(task)
    if fasta_path:
        try:
            with open(fasta_path, 'rb') as fasta_file:
                fasta_data = fasta_file.read()
            filename = os.path.basename(fasta_path)
            response = HttpResponse(fasta_data, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception:
            messages.error(request, 'Could not read the FASTA file. Please try again later.')
            return redirect('conversion:task_status', task_id=task.id)
    else:
        messages.error(request, 'FASTA file is not available for download.')
        return redirect('conversion:task_status', task_id=task.id)

@require_POST
@login_required
def rename_process_view(request, task_id):
    task = get_object_or_404(_get_current_user_tasks(request), id=task_id)
    new_name = (request.POST.get('process_name') or '').strip()
    if not new_name:
        messages.error(request, 'Process name cannot be empty.')
        return redirect('conversion:task_status', task_id=task.id)

    rename_process_group(request.user, task, new_name)
    messages.success(request, 'Process name updated.')
    return redirect('conversion:task_status', task_id=task.id)


