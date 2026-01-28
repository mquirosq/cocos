from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest

from .models import AnnotationTask
from .services import annotate_from_fasta
from .tasks import poll_external_task


def external_task_ui(request):
    """Handle GET (render UI) and POST (start task) on the same URL.

    GET: render the upload page.
    POST: expect `fasta_file` in multipart form-data and return JSON with created `task_id`.
    """
    if request.method == 'POST':
        fasta = request.FILES.get('fasta_file')
        if not fasta:
            return HttpResponseBadRequest('No fasta_file uploaded')

        fasta_bytes = fasta.read()
        external_resp = annotate_from_fasta(fasta_bytes)

        # TODO: Improve input/output management
        task = AnnotationTask.objects.create(
            external_job_id=external_resp.get('job_id') if isinstance(external_resp, dict) else None,
            status='pending',
            input_path='uploaded_via_ui',
        )

        poll_external_task.delay(task.id)
        return JsonResponse({'task_id': task.id})

    return render(request, 'converter/start_external_task.html')


def task_status(request, task_id):
    """Return JSON with the current status for a task."""
    task = get_object_or_404(AnnotationTask, id=task_id)
    return JsonResponse({
        'task_id': task.id,
        'status': task.status,
        'external_id': task.external_job_id,
    })
