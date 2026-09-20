import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..models import ConversionTask, File, ProcessGroup
from ..parsers import parse_file
from ..services.status import get_available_fasta_jobs, has_annotation_for_previous
from ..tasks import (
    poll_annotation_from_assembly_start,
    poll_annotation_start,
    poll_assembly_start,
)
from ..utils import upload_file, get_current_user_tasks

def _annotation_context(request, active_tab='fasta', **extra):
    context = {
        'active_tab': active_tab,
        'available_fasta_jobs': get_available_fasta_jobs(request.user),
    }
    context.update(extra)
    return context


def _start_annotation_from_source_job(request, source_job_id):
    available_jobs = get_available_fasta_jobs(request.user)
    source_task = next((task for task in available_jobs if task.external_job_id == source_job_id), None)
    
    if not source_task:
        messages.error(request, 'Selected FASTA is not available for annotation.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    if has_annotation_for_previous(source_task):
        messages.error(request, 'This FASTA output already has an annotation task.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    if source_task.process.user != request.user:
        messages.error(request, 'You do not have permission to annotate this FASTA output.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))
    
    if source_task.status != ConversionTask.TaskStatus.COMPLETED:
        messages.error(request, 'Selected FASTA output is not ready for annotation.')
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

    task = ConversionTask.objects.create(
        external_job_id=None,
        status=ConversionTask.TaskStatus.PENDING,
        task_type=ConversionTask.TaskType.ANNOTATION,
        process=source_task.process,
    )
    task.input_files.set(source_task.output_files.all())

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
    file = upload_file(
        fasta,
        user=request.user,
        file_type=File.FileType.FASTA
    )

    process = ProcessGroup.objects.create(name=os.path.basename(file.file.name), user=request.user)
    task = ConversionTask.objects.create(
        external_job_id=None,
        status=ConversionTask.TaskStatus.PENDING,
        task_type=ConversionTask.TaskType.ANNOTATION,
        process=process
    )

    task.input_files.add(file)

    poll_annotation_start.delay(
        fasta_bytes=fasta_bytes,
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

    assembly_type = request.POST.get('assembly_type')
    annotate = request.POST.get('annotate') == 'on'

    fastq = request.FILES.get('fastq_file')
    if not fastq:
        messages.error(request, 'No FASTQ file uploaded.')
        return redirect('conversion:assembly_ui')

    fastq_2 = request.FILES.get('fastq_file_2')

    if assembly_type != 'illumina' and fastq_2:
        messages.error(
            request,
            'Second FASTQ file is only valid for Illumina assembly.'
        )
        return redirect('conversion:assembly_ui')

    file_1 = upload_file(
        fastq,
        user=request.user,
        file_type=File.FileType.FASTQ,
    )

    file_2 = None
    if fastq_2:
        file_2 = upload_file(
            fastq_2,
            user=request.user,
            file_type=File.FileType.FASTQ,
        )

    process = ProcessGroup.objects.create(name=os.path.basename(fastq.name), user=request.user)
    task = ConversionTask.objects.create(
        external_job_id=None,
        status=ConversionTask.TaskStatus.PENDING,
        task_type=f"assembly_{assembly_type}{'_annotated' if annotate else ''}",
        process = process,
    )

    task.input_files.add(file_1)

    if file_2:
        task.input_files.add(file_2)

    poll_assembly_start.delay(
        assembly_type=assembly_type,
        file_id_1=file_1.id,
        file_id_2=file_2.id if file_2 else None,
        annotate=annotate,
        task_id=task.id,
        complete_version=request.POST.get('complete') == 'on',
    )

    message = (
        f"Assembly task started for file {fastq.name}. "
        "You will be notified when it's complete."
    )
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

    source_task = get_current_user_tasks(request).filter(
        external_job_id=job_id,
        status=ConversionTask.TaskStatus.COMPLETED,
        task_type__in=(ConversionTask.TaskType.ASSEMBLY_ILLUMINA, ConversionTask.TaskType.ASSEMBLY_ONT),
    ).first()
    if not source_task:
        messages.error(request, 'Assembly job not found or not available for annotation.')
        return redirect('conversion:annotation_ui')

    if has_annotation_for_previous(source_task):
        messages.warning(request, 'This assembly result already has an annotation task.')
        return redirect('conversion:annotation_ui')
    
    if source_task.process.user != request.user:
        messages.error(request, 'You do not have permission to annotate this assembly result.')
        return redirect('conversion:annotation_ui')
    
    if source_task.status != ConversionTask.TaskStatus.COMPLETED:
        messages.error(request, 'Selected assembly job is not ready for annotation.')
        return redirect('conversion:annotation_ui')

    task = ConversionTask.objects.create(
        external_job_id=None,
        status=ConversionTask.TaskStatus.PENDING,
        task_type=ConversionTask.TaskType.ANNOTATION,
        process=source_task.process,
    )
    task.input_files.set(source_task.output_files.all())

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

        file = upload_file(feature_file, user=request.user, file_type=File.FileType.JSON)

        process = ProcessGroup.objects.create(name=os.path.basename(file.file.name), user=request.user)
        task = ConversionTask.objects.create(
            status=ConversionTask.TaskStatus.PENDING,
            task_type=ConversionTask.TaskType.FROM_JSON,
            process=process,
        )

        task.input_files.add(file)

        complete_version = request.POST.get('complete') == 'on'

        # Read the file
        try:
            with file.file.open('rb') as stored_file:
                data = json.load(stored_file)

        except Exception:
            task.status = ConversionTask.TaskStatus.FAILED
            task.save(update_fields=['status', 'updated_at'])

            messages.error(request, 'Error decoding JSON file.')

            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))

        try:
            file_upload = parse_file("bakta_json", data, file, user=request.user,
                    options={"complete_version": complete_version}
                )

        except Exception as e:
            task.status = ConversionTask.TaskStatus.FAILED
            task.save(update_fields=['status', 'updated_at'])
            messages.error(request, f'Error parsing features. Try again later.')
            return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='json'))

        task.status = ConversionTask.TaskStatus.COMPLETED
        task.save(update_fields=['status', 'updated_at'])

        messages.success(request, 'File parsed successfully!')

        return render(
            request,
            'conversion/annotation.html',
            _annotation_context(
                request,
                active_tab='json',
                file_upload=file_upload
            )
        )

    return redirect('conversion:annotation_ui')

