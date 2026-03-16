from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.contrib import messages
from django.views.decorators.http import require_POST

from .utils import upload_file
import json
from .parsers import parse_file
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseServerError
from .services import download_bakta_json_result
import json
from .models import ConversionTask

def conversion_task_ui(request):
    """Render a simple UI for starting external tasks like annotation and sequencing."""
    return render(request, 'converter/start_external_task.html')

@require_POST
def annotation_task(request):
    """
    Allow users to upload a FASTA file via a simple web form to start an external annotation task.
    On submission, create an AnnotationTask and trigger polling of its status.
    """
    if request.method == 'POST':
        fasta = request.FILES.get('fasta_file')
        if not fasta:
            return HttpResponseBadRequest('No fasta_file uploaded')

        fasta_bytes = fasta.read()
        
        dest_path = upload_file(fasta, upload_dir='uploads/fasta')

        # Create a pending ConversionTask immediately so the UI shows the task.
        task = ConversionTask.objects.create(
            external_job_id=None,
            status='pending',
            input_path=dest_path,
            task_type='annotation'
        )

        # Start the annotation task asynchronously (import tasks lazily to avoid app registry issues)
        from .tasks import poll_annotation_start
        poll_annotation_start.delay(fasta_bytes, dest_path, task.id)

        message = f"Annotation task started for file {fasta.name}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('conversion:conversion_task_ui')

@require_POST
def sequencing_task(request):
    """
    Allow users to upload a FASTQ file via a simple web form to start an external sequencing task.
    On submission, create a SequencingTask and trigger polling of its status.
    """
    if request.method == 'POST':
        print("Received sequencing task request")
        sequencing_type = request.POST.get('sequencing_type')
        annotate = request.POST.get('annotate') == 'on'  # Checkbox value

        fastq = request.FILES.get('fastq_file')
        if not fastq:
            return HttpResponseBadRequest('No fastq_file uploaded')

        fastq_2 = request.FILES.get('fastq_file_2')  # For Illumina
        if not sequencing_type == "illumina" and fastq_2:
            return HttpResponseBadRequest('Second FASTQ file provided for non-Illumina sequencing type')
        
        dest_path = upload_file(fastq, upload_dir='uploads/fastq')
        dest_path_2 = None
        if fastq_2:
            dest_path_2 = upload_file(fastq_2, upload_dir='uploads/fastq')
        
        # Create a pending ConversionTask so it appears in the UI immediately.
        task = ConversionTask.objects.create(
            external_job_id=None,
            status='pending',
            input_path=dest_path + ("," + dest_path_2 if dest_path_2 else ""),
            task_type="sequencing" + ("_" + sequencing_type) + ("_annotated" if annotate else "")
        )

        # Start the sequencing task asynchronously (lazy import)
        print(f"Starting sequencing task with type {sequencing_type} for file {fastq.name}")
        from .tasks import poll_sequencing_start
        poll_sequencing_start.delay(sequencing_type, dest_path, dest_path_2, annotate, task.id)

        message = f"Sequencing task started for file {fastq.name}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('conversion:conversion_task_ui')
    
@require_POST
def annotation_from_sequencing_task(request, job_id):
    """
    Start an annotation task based on the result of a previous sequencing task.
    Expects a job_id from the sequencing task to be provided in the POST data.
    """
    if request.method == 'POST':
        if not job_id:
            return HttpResponseBadRequest('No job_id provided for annotation task')

        print(f"Starting annotation task from sequencing job with ID: {job_id}")

        # Create pending annotation task in DB so UI reflects it immediately
        task = ConversionTask.objects.create(
            external_job_id=None,
            status='pending',
            input_path='',
            task_type='annotation'
        )

        from .tasks import poll_annotation_from_sequencing_start
        poll_annotation_from_sequencing_start.delay(job_id, task.id)

        message = f"Annotation task started for sequencing job {job_id}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('conversion:conversion_task_ui')


def parse_feature_file(request):
    """View to handle feature file parsing (keeps legacy URL name)."""
    if request.method == 'POST':
        complete_version = request.POST.get('complete') == 'on'
        try:
            data = json.load(request.FILES.get('feature_file'))
        except Exception:
            return render(None, 'featureParser/parse_feature_file.html', {'messages': ['Error decoding JSON file!']})
        
        file_upload = parse_file("bakta_json", data, request.FILES.get('feature_file'), {"complete_version": complete_version})
        return render(request, 'featureParser/parse_feature_file.html', {'messages': ['File parsed successfully!'], 'file_upload': file_upload})
    return render(request, 'featureParser/parse_feature_file.html')


# --- Task list / detail / download views moved from model ---
def task_list_view(request):
    """Render a list of annotation tasks as cards including external_job_id and status."""
    tasks = ConversionTask.objects.all().order_by('-id')
    return render(request, 'model/task_list.html', {'tasks': tasks})


def task_status_view(request, task_id):
    task = ConversionTask.objects.get(id=task_id)
    return render(request, 'model/task_status.html', {'task': task})


def download_json_view(request, task_id):
    """
    Download the Bakta JSON result for a completed task as an attachment.
    """
    task = get_object_or_404(ConversionTask, id=task_id)
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
