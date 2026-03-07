from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from model.models import FileUpload

from .parser import get_model_features_from_columns, presence_from_list, get_prediction_for_antibiotic, process_column_names


def presence_test(request):
	"""HTTP endpoint to test `presence_from_list`.

	Query params:
	  - features: comma-separated feature names (optional)
	  - file_id: id of `FileUpload` to test (optional)

	Returns JSON with `model_features` and `presence_vector`.
	"""
	features = request.GET.get('features')
	if features:
		model_features = [f.strip() for f in features.split(',') if f.strip()]
	else:
		model_features = ["kgtP", "l-aspartate oxidase", "geneC"]

	file_id = request.GET.get('file_id')
	try:
		if file_id:
			file_upload = FileUpload.objects.filter(pk=int(file_id)).first()
		else:
			file_upload = FileUpload.objects.first()
	except ValueError:
		return HttpResponseBadRequest('Invalid file_id')

	presence_vector = presence_from_list(model_features, file_upload)

	return JsonResponse({
		'model_features': model_features,
		'presence_vector': presence_vector,
		'file_id': file_upload.pk if file_upload is not None else None,
	})



def presence_from_columns_test(request):
	"""Load model features from `bakta50_columns.pkl` and return a presence vector.

	Query params:
	  - file_id: id of `FileUpload` to test (optional)

	Returns JSON with `model_features` and `presence_vector`.
	"""
	model_features, _, _ = get_model_features_from_columns('bakta50_columns.pkl')

	model_features = process_column_names(model_features)

	file_id = request.GET.get('file_id')
	try:
		if file_id:
			file_upload = FileUpload.objects.filter(pk=int(file_id)).first()
		else:
			file_upload = FileUpload.objects.filter(pk=24).first()  # Adjust default ID as needed
	except ValueError:
		return HttpResponseBadRequest('Invalid file_id')

	presence_vector = presence_from_list(model_features, file_upload)

	return JsonResponse({
		'model_features': model_features,
		'model_features_count': len(model_features),
		'presence_vector': presence_vector,
		'file_id': file_upload.pk if file_upload is not None else None,
	})


def prediction_view(request):
	"""Render a UI and run `get_prediction_for_antibiotic`.

	POST params: `model_name`, `antibiotic`, optional `file_id`.
	If `model_name` is provided, the prediction will be computed and shown.
	"""
	model_name = None
	antibiotic = None
	file_upload = None

	if request.method == 'POST':
		model_name = request.POST.get('model_name')
		antibiotic = request.POST.get('antibiotic') or None
		file_id = request.POST.get('file_id') or None
	else:
		model_name = request.GET.get('model_name')
		antibiotic = request.GET.get('antibiotic') or None
		file_id = request.GET.get('file_id') or None

	if file_id:
		try:
			file_upload = FileUpload.objects.filter(pk=int(file_id)).first()
		except ValueError:
			return HttpResponseBadRequest('Invalid file_id')

	prediction = None
	error = None
	if model_name:
		try:
			prediction = get_prediction_for_antibiotic(model_name, antibiotic, None, file_upload)
		except Exception as e:
			error = str(e)

	return render(request, 'inputParser/prediction.html', {
		'prediction': prediction,
		'error': error,
		'model_name': model_name,
		'antibiotic': antibiotic,
		'file_id': getattr(file_upload, 'pk', None) if file_upload is not None else None,
	})