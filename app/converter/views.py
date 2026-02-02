from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
import os
import uuid
from django.utils.text import get_valid_filename
from django.contrib import messages

from .tasks import poll_annotation_start

# TODO: Move upload logic to a separate utility module (so it can be reused)
def external_task_ui(request):
    """
    Allow users to upload a FASTA file via a simple web form to start an external annotation task.
    On submission, create an AnnotationTask and trigger polling of its status.
    """
    if request.method == 'POST':
        fasta = request.FILES.get('fasta_file')
        if not fasta:
            return HttpResponseBadRequest('No fasta_file uploaded')

        fasta_bytes = fasta.read()
        
        # Uploads FASTA into uploads/fasta, creating dir and avoiding collisions
        upload_dir = os.path.join('uploads', 'fasta')
        os.makedirs(upload_dir, exist_ok=True)

        safe_name = get_valid_filename(fasta.name) # Makes filename safe
        dest_path = os.path.join(upload_dir, safe_name)
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(safe_name)
            dest_path = os.path.join(upload_dir, f"{base}_{uuid.uuid4().hex}{ext}")

        # Upload the file
        with open(dest_path, 'wb') as f:
            f.write(fasta_bytes)

        # Start the annotation task asynchronously
        poll_annotation_start.delay(fasta_bytes, dest_path)

        message = f"Annotation task started for file {fasta.name}. You will be notified when it's complete."
        messages.info(request, message)

        return redirect('task_list')

    return render(request, 'converter/start_external_task.html')