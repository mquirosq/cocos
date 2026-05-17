from .registry import get_model_adapter_class

def get_prediction(model_name: str, antibiotic: str, file_upload) -> float:
    model_cls = get_model_adapter_class(model_name)
    if not model_cls:
        raise ValueError(f'Model {model_name} not found in registry.')

    adapter = model_cls(antibiotic=antibiotic)

    adapter.load()
    return adapter.predict(file_upload)

def get_prediction_matrix(model_names: list[str], antibiotics: list[str], file_upload) -> dict:
    """
    Compute a prediction matrix for the given models, antibiotics, and file upload.
    Returns a dict of the form:
    {
        'antibiotic1': {
            'model1': prediction_value or 'NO_RESULT',
            'model2': prediction_value or 'NO_RESULT',
            ...
        },
        'antibiotic2': {
            ...
        },
        ...
    }
    """
    data = {}
    for antibiotic in antibiotics:
        row = {}
        for model_name in model_names:
            try:
                row[model_name] = get_prediction(model_name, antibiotic, file_upload)
            except Exception as e:
                row[model_name] = 'NO_RESULT'
        data[antibiotic] = row

    return data