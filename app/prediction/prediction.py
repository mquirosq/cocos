import logging

from .registry import get_model_adapter_class

logger = logging.getLogger(__name__)


def get_prediction(model_name: str, antibiotic: str, file) -> float:
    model_cls = get_model_adapter_class(model_name)
    if not model_cls:
        raise ValueError(f'Model {model_name} not found in registry.')

    adapter = model_cls(antibiotic=antibiotic)

    adapter.load()
    return adapter.predict(file)

def get_prediction_matrix(model_names: list[str], antibiotics: list[str], file) -> dict:
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
                row[model_name] = get_prediction(model_name, antibiotic, file)
            except Exception as e:
                logger.exception(f'Prediction failed for models={model_name}, antibiotic={antibiotic}', exc_info=True)
                row[model_name] = 'NO_RESULT'
        data[antibiotic] = row

    return data