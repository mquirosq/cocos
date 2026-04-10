import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ConversionTask
from .parsers import parse_file
from .services import download_bakta_json_result
from .tasks import (
    poll_annotation_from_sequencing_start,
    poll_annotation_start,
    poll_sequencing_start,
)
from .utils import resolve_persisted_result_filename, upload_file

def _get_current_user_tasks(request):
    """Return tasks filtered by authenticated user."""
    return ConversionTask.objects.filter(user=request.user)


def _get_available_fasta_jobs(user):
    """Return completed base sequencing jobs that are not already annotated."""
    completed_sequencing_tasks = ConversionTask.objects.filter(
        user=user,
        status='completed',
        task_type__in=('sequencing_illumina', 'sequencing_ont'),
        external_job_id__isnull=False,
    ).exclude(external_job_id='').order_by('-updated_at', '-id')

    already_annotated_ids = ConversionTask.objects.filter(
        user=user,
        task_type='annotation',
        status__in=('pending', 'running', 'completed'),
        previous_task__isnull=False,
    ).values_list('previous_task_id', flat=True)

    available_tasks = list(completed_sequencing_tasks.exclude(id__in=already_annotated_ids))

    for task in available_tasks:
        resolved_name = resolve_persisted_result_filename(
            user_id=user.id,
            result_prefix='assembly',
            job_id=task.external_job_id,
        )
        task.source_filename = resolved_name or 'Assembly output'

    return available_tasks


def _annotation_context(request, active_tab='fasta', **extra):
    context = {
        'active_tab': active_tab,
        'available_fasta_jobs': _get_available_fasta_jobs(request.user),
    }
    context.update(extra)
    return context


def _has_annotation_for_previous(user, previous_task):
    return ConversionTask.objects.filter(
        user=user,
        task_type='annotation',
        status__in=('pending', 'running', 'completed'),
        previous_task=previous_task,
    ).exists()


def _start_annotation_from_source_job(request, source_job_id):
    available_jobs = _get_available_fasta_jobs(request.user)
    previous_task = next((task for task in available_jobs if task.external_job_id == source_job_id), None)
    if not previous_task:
        messages.error(request, 'Selected FASTA is not available for annotation.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    if _has_annotation_for_previous(request.user, previous_task):
        messages.error(request, 'This FASTA output already has an annotation task.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    task = ConversionTask.objects.create(
        external_job_id=None,
        status='pending',
        input_path=previous_task.input_path,
        task_type='annotation',
        user=request.user,
        previous_task=previous_task,
    )

    poll_annotation_from_sequencing_start.delay(
        job_id=source_job_id,
        user_id=request.user.id,
        new_task_id=task.id,
    )

    message = f"Annotation task started from previous assembly job {source_job_id}. You will be notified when it's complete."
    messages.info(request, message)
    return redirect('conversion:annotation_ui')


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
    )

    poll_annotation_start.delay(
        fasta_bytes=fasta_bytes,
        dest_path=dest_path,
        task_id=task.id,
    )

    message = f"Annotation task started for file {fasta.name}. You will be notified when it's complete."
    messages.info(request, message)
    return redirect('conversion:annotation_ui')

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
def sequencing_task(request):
    """
    Allow users to upload a FASTQ file via a simple web form to start an external sequencing task.
    On submission, create a SequencingTask and trigger polling of its status.
    """
    print("Received sequencing task request")
    sequencing_type = request.POST.get('sequencing_type')
    annotate = request.POST.get('annotate') == 'on'  # Checkbox value

    fastq = request.FILES.get('fastq_file')
    if not fastq:
        messages.error(request, 'No FASTQ file uploaded.')
        return redirect('conversion:assembly_ui')

    fastq_2 = request.FILES.get('fastq_file_2')  # For Illumina
    if sequencing_type != 'illumina' and fastq_2:
        messages.error(request, 'Second FASTQ file is only valid for Illumina sequencing.')
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
        task_type=f"sequencing_{sequencing_type}{'_annotated' if annotate else ''}",
        user=request.user,
    )

    print(f"Starting sequencing task with type {sequencing_type} for file {fastq.name}")
    poll_sequencing_start.delay(
        sequencing_type=sequencing_type,
        dest_path=dest_path,
        dest_path_2=dest_path_2,
        annotate=annotate,
        task_id=task.id,
    )

    message = f"Sequencing task started for file {fastq.name}. You will be notified when it's complete."
    messages.info(request, message)

    return redirect('conversion:assembly_ui')
    
@require_POST
@login_required
def annotation_from_sequencing_task(request, job_id):
    """
    Start an annotation task based on the result of a previous sequencing task.
    Expects a job_id from the sequencing task to be provided in the POST data.
    """
    if not job_id:
        messages.error(request, 'No sequencing job id was provided for annotation.')
        return redirect('conversion:annotation_ui')

    print(f"Starting annotation task from sequencing job with ID: {job_id}")

    previous_task = _get_current_user_tasks(request).filter(
        external_job_id=job_id,
        status='completed',
        task_type__in=('sequencing_illumina', 'sequencing_ont'),
    ).first()
    if not previous_task:
        messages.error(request, 'Sequencing job not found or not available for annotation.')
        return redirect('conversion:annotation_ui')

    if _has_annotation_for_previous(request.user, previous_task):
        messages.warning(request, 'This sequencing result already has an annotation task.')
        return redirect('conversion:annotation_ui')

    task = ConversionTask.objects.create(
        external_job_id=None,
        status='pending',
        input_path=previous_task.input_path,
        task_type='annotation',
        user=request.user,
        previous_task=previous_task,
    )

    poll_annotation_from_sequencing_start.delay(
        user_id=request.user.id,
        job_id=job_id,
        new_task_id=task.id,
    )

    message = f"Annotation task started for sequencing job {job_id}. You will be notified when it's complete."
    messages.info(request, message)
    return redirect('conversion:annotation_ui')


@login_required
def parse_feature_file(request):
    """Handle Bakta JSON parsing from Annotation tab."""
    if request.method == 'POST':
        complete_version = request.POST.get('complete') == 'on'
        try:
            data = json.load(request.FILES.get('feature_file'))
        except Exception:
            messages.error(request, 'Error decoding JSON file.')
            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))
        
        try:
            file_upload = parse_file(
                "bakta_json",
                data,
                request.FILES.get('feature_file'),
                user=request.user,
                options={"complete_version": complete_version}
            )
        except Exception as e:
            messages.error(request, f'Error parsing features: {e}')
            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))

        messages.success(request, 'File parsed successfully!')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json', file_upload=file_upload))
    return redirect('conversion:annotation_ui')

# Tasks
@login_required
def task_list_view(request):
    """Render a list of annotation tasks as cards including external_job_id and status."""
    tasks = _get_current_user_tasks(request).order_by('-id')
    annotated_source_ids = list(
        tasks.filter(
            task_type='annotation',
            status__in=['pending', 'running', 'completed'],
            previous_task__isnull=False,
        ).values_list('previous_task_id', flat=True)
    )
    return render(request, 'conversion/task_list.html', {
        'tasks': tasks,
        'annotated_source_ids': annotated_source_ids,
    })


@login_required
def task_status_view(request, task_id):
    task = get_object_or_404(_get_current_user_tasks(request), id=task_id)
    has_annotation_descendant = _get_current_user_tasks(request).filter(
        task_type='annotation',
        status__in=['pending', 'running', 'completed'],
        previous_task=task,
    ).exists()
    return render(request, 'conversion/task_status.html', {
        'task': task,
        'has_annotation_descendant': has_annotation_descendant,
    })


@login_required
def download_json_view(request, task_id):
    """
    Download the Bakta JSON result for a completed task as an attachment.
    """
    task = get_object_or_404(_get_current_user_tasks(request), id=task_id)
    if task.status != 'completed':
        return redirect('conversion:task_status', task_id=task.id)
    try:
        json_data = download_bakta_json_result(task.external_job_id)
    except Exception:
        return HttpResponseServerError('Failed to download annotation results')

    if isinstance(json_data, (dict, list)):
        content = json.dumps(json_data)
    else:
        content = str(json_data)

    response = HttpResponse(content, content_type='application/json')
    filename = f'annotation_{task.external_job_id}.json'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

