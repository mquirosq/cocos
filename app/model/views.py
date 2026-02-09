from django.shortcuts import render, redirect, get_object_or_404
from converter.models import ConversionTask
from django.http import HttpResponse, HttpResponseServerError
from converter.services import download_bakta_json_result
import json

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
        return redirect('task_status', task_id=task.id)
    try:
        json_data = download_bakta_json_result(task.external_job_id)
    except Exception:
        return HttpResponseServerError('Failed to download annotation results')

    # If the service returned a Python object, serialize it; otherwise assume it's JSON text
    if isinstance(json_data, (dict, list)):
        content = json.dumps(json_data)
    else:
        content = str(json_data)

    response = HttpResponse(content, content_type='application/json')
    filename = f'annotation_{task.external_job_id}.json'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
