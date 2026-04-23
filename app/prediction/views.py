import json
import os
import csv

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from conversion.models import FileUpload
from .registry import list_registered_models, get_model_supported_antibiotics, list_all_antibiotics
from .service import get_prediction_matrix
from django.contrib import messages as message
from django.http import HttpResponse

def _get_user_json_uploads(user):
    return FileUpload.objects.filter(
        user=user,
        file__iendswith='.json',
    ).order_by('-uploaded_at')

@login_required
def prediction_view(request):
    json_uploads = _get_user_json_uploads(request.user)

    input_file_options = [
        {
            'id': str(upload.pk),
            'file_name': os.path.basename(upload.file.name),
            'uploaded_at': upload.uploaded_at,
        }
        for upload in json_uploads
    ]

    available_models = list_registered_models()
    available_antibiotics = list_all_antibiotics()

    return render(request, 'prediction/prediction.html', {
        'input_file_options': input_file_options,
        'available_models': available_models,
        'available_antibiotics': available_antibiotics,
    })


@login_required
@require_POST
def prediction_matrix_view(request):
    model_names = request.POST.getlist('models')
    antibiotics = request.POST.getlist('antibiotics')
    file_id = request.POST.get('file_id', '').strip() or None

    if not model_names:
        return JsonResponse({'error': 'Select at least one model.'}, status=400)
    if not antibiotics:
        return JsonResponse({'error': 'Select at least one antibiotic.'}, status=400)

    file_upload = None
    if file_id:
        try:
            file_upload = FileUpload.objects.get(
                pk=int(file_id),
                user=request.user,
                file__iendswith='.json',
            )
        except (ValueError, FileUpload.DoesNotExist):
            return JsonResponse({'error': 'Selected file not found.'}, status=400)

    # Validate all requested antibiotics are supported by all requested models
    valid_antibiotics = [
        antibiotic for antibiotic in antibiotics
        if any(antibiotic in get_model_supported_antibiotics(m) for m in model_names)
    ]
    if not valid_antibiotics:
        return JsonResponse({'error': 'No valid antibiotic/model combinations found.'}, status=400)

    try:
        matrix = get_prediction_matrix(
            model_names=model_names,
            antibiotics=valid_antibiotics,
            file_upload=file_upload,
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse(matrix)

@login_required
@require_POST
def prediction_csv_from_matrix_view(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    matrix = body
    if not isinstance(matrix, dict):
        return JsonResponse({'error': 'Invalid matrix payload.'}, status=400)

    models = matrix.get('models')
    antibiotics = matrix.get('antibiotics')
    data = matrix.get('data')

    if not (isinstance(models, list) and isinstance(antibiotics, list) and isinstance(data, list)):
        return JsonResponse({'error': 'Invalid matrix structure.'}, status=400)

    if len(antibiotics) != len(data):
        return JsonResponse({'error': 'Matrix data size mismatch.'}, status=400)

    for row in data:
        if not isinstance(row, list) or len(row) != len(models):
            return JsonResponse({'error': 'Matrix rows must match models length.'}, status=400)

    # Build CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="predictions.csv"'

    writer = csv.writer(response)
    writer.writerow(['Antibiotic'] + models + ['Average'])

    for i, antibiotic in enumerate(antibiotics):
        vals = data[i]
        try:
            avg = round(sum(float(v) for v in vals) / len(vals), 4)
        except Exception:
            avg = ''
        writer.writerow([antibiotic] + [round(float(v), 4) for v in vals] + [avg])

    return response