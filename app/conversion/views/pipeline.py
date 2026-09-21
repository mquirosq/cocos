import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..models import ConversionTask, File, ProcessGroup
from ..parsers import parse_file
from ..services.pipeline import  get_assembly_tasks_can_be_annotated, start_annotation_from_assembly_task, start_annotation_from_uploaded_fasta
from ..utils import upload_file
from ..tasks import (
    poll_assembly_start,
)

def _annotation_context(request, active_tab='fasta', **extra):
    context = {
        'active_tab': active_tab,
        'available_fasta_jobs': get_assembly_tasks_can_be_annotated(request.user),
    }
    context.update(extra)
    return context


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
def start_annotation_task(request):
    """
    Allow users to upload a FASTA file via a simple web form to start an external annotation task.
    On submission, create an AnnotationTask and trigger polling of its status.
    """
    source_job_id = (request.POST.get('source_job_id') or '').strip()
    fasta = request.FILES.get('fasta_file')
    complete_version = request.POST.get('complete') == 'on'

    try:
        if source_job_id:
            task = start_annotation_from_assembly_task(request.user, source_job_id, complete_version,)
            message = (f'Annotation task started from previous assembly job {source_job_id}. You will be notified when it is complete.')
        else:
            task = start_annotation_from_uploaded_fasta(request.user, fasta, complete_version)
            message = (f'Annotation task started for file {fasta.name}. You will be notified when it is complete.')

    except ValueError as e:
        messages.error(request, str(e))
        return render(request, 'conversion/annotation.html', _annotation_context(request, active_tab='fasta'))

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

