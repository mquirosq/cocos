import json
import csv

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .service import get_prediction_input_options, start_prediction, prepare_prediction_csv
from .registry import list_registered_models, list_all_antibiotics

@login_required
def prediction_view(request):
    return render(request, 'prediction/prediction.html', {
        'input_file_options': get_prediction_input_options(request.user),
        'available_models': list_registered_models(),
        'available_antibiotics': list_all_antibiotics(),
    })

@login_required
@require_POST
def prediction_matrix_view(request):
    model_names = request.POST.getlist('models')
    antibiotics = request.POST.getlist('antibiotics')
    file_id = request.POST.get('file_id', '').strip() or None

    try:
        matrix = start_prediction(
            user=request.user,
            model_names=model_names,
            antibiotics=antibiotics,
            file_id=file_id,
        )
    except ValueError as e:
        messages.error(request, str(e))
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        messages.error(request, str(e))
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse(matrix)

@login_required
@require_POST
def prediction_csv_from_matrix_view(request):
    try:
        matrix = json.loads(request.body)
        models, rows = prepare_prediction_csv(matrix)
    except json.JSONDecodeError:
        messages.error(request, 'Invalid JSON.')
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    except ValueError as e:
        messages.error(request, str(e))
        return JsonResponse({'error': str(e)}, status=400)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = ('attachment; filename="predictions.csv"')

    writer = csv.writer(response)
    writer.writerow(['Antibiotic'] + models + ['Average'])

    writer.writerows(rows)

    return response