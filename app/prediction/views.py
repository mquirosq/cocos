from django.shortcuts import render
from pathlib import Path
from conversion.models import FileUpload
from .service import get_prediction
from .registry import list_registered_models, get_model_adapter_class
from django.contrib.auth.decorators import login_required

@login_required()
def prediction_view(request):
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
            file_upload = FileUpload.objects.filter(pk=int(file_id)).filter(user=request.user).first()
        except (ValueError, TypeError):
            file_upload = None

    prediction = None
    error = None
    available_antibiotics = []
    if model_name:
        model_cls = get_model_adapter_class(model_name)
        if not model_cls:
            error = f"Model '{model_name}' not found."
        else:
            available_antibiotics = []
            try:
                base_dir = Path(__file__).resolve().parents[1]
                ai_root = base_dir / 'ai_models'
                model_dir = ai_root / model_name
                if not (model_dir.exists() and model_dir.is_dir()):
                    norm = model_name.replace('-', '_')
                    for d in ai_root.iterdir() if ai_root.exists() else []:
                        if not d.is_dir():
                            continue
                        if d.name.lower().replace('-', '_') == norm.lower():
                            model_dir = d
                pesos_dir = model_dir / 'pesos'
                if pesos_dir.exists() and pesos_dir.is_dir():
                    available_antibiotics = sorted({p.stem for p in pesos_dir.glob('*.pt')})
            except Exception:
                available_antibiotics = []

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
