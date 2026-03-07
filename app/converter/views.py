from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.contrib import messages
from django.views.decorators.http import require_POST

from .tasks import poll_annotation_from_sequencing_start, poll_annotation_start, poll_sequencing_start
from .utils import upload_file

# TODO: Move upload logic to a separate utility module (so it can be reused)
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

        # Start the annotation task asynchronously
        poll_annotation_start.delay(fasta_bytes, dest_path)

        message = f"Annotation task started for file {fasta.name}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('task_list')

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
        
        # Start the sequencing task asynchronously
        print(f"Starting sequencing task with type {sequencing_type} for file {fastq.name}")
        poll_sequencing_start.delay(sequencing_type, dest_path, dest_path_2, annotate=annotate)

        message = f"Sequencing task started for file {fastq.name}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('task_list')
    
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
        poll_annotation_from_sequencing_start.delay(job_id)

        message = f"Annotation task started for sequencing job {job_id}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('task_list')