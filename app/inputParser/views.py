from django.shortcuts import render
from django.http import HttpResponseBadRequest
from pathlib import Path
from model.models import FileUpload
from .service import get_prediction
from .registry import list_registered_models, get_model_adapter_class

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
		if model_name:
			model_name = model_name.strip().lower()
		antibiotic = request.POST.get('antibiotic') or None
		file_id = request.POST.get('file_id') or None
	else:
		model_name = request.GET.get('model_name')
		if model_name:
			model_name = model_name.strip().lower()
		antibiotic = request.GET.get('antibiotic') or None
		file_id = request.GET.get('file_id') or None

	if file_id:
		try:
			file_upload = FileUpload.objects.filter(pk=int(file_id)).first()
		except (ValueError, TypeError):
			# Ignore invalid file_id values (don't abort page); treat as no FileUpload
			file_upload = None

	prediction = None
	error = None
	available_antibiotics = []
	# Only attempt prediction if a model name was provided and is registered
	if model_name:
		model_cls = get_model_adapter_class(model_name)
		if not model_cls:
			error = f"Model '{model_name}' not found."
		else:
			# Build list of available antibiotics from ai_models/<model_name>/pesos/*.pt
			available_antibiotics = []
			try:
				base_dir = Path(__file__).resolve().parents[1]
				ai_root = base_dir / 'ai_models'
				# Try to find the model directory robustly: exact, or by replacing '-' with '_' or viceversa
				model_dir = ai_root / model_name
				if not (model_dir.exists() and model_dir.is_dir()):
					# normalize names for loose matching
					norm = model_name.replace('-', '_')
					# search directories under ai_root for a normalized match
					for d in ai_root.iterdir() if ai_root.exists() else []:
						if not d.is_dir():
							continue
						if d.name.lower().replace('-', '_') == norm.lower():
							model_dir = d
				# final pesos dir
				pesos_dir = model_dir / 'pesos'
				if pesos_dir.exists() and pesos_dir.is_dir():
					available_antibiotics = sorted({p.stem for p in pesos_dir.glob('*.pt')})
			except Exception:
				available_antibiotics = []

			# Only run prediction when an antibiotic value was provided by the user
			if antibiotic:
				try:
					prediction = get_prediction(model_name=model_name, antibiotic=antibiotic, file_upload=file_upload)
				except Exception as e:
					error = str(e)

	return render(request, 'inputParser/prediction.html', {
		'prediction': prediction,
		'error': error,
		'model_name': model_name,
		'antibiotic': antibiotic,
		'available_models': list_registered_models(),
		'available_antibiotics': available_antibiotics,
		'file_id': getattr(file_upload, 'pk', None) if file_upload is not None else None,
	})