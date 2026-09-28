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
    Compute a prediction matrix for the given models, antibiotics, and file.
    Returns a dict of the form:
    {
        'models': [...],
        'antibiotics': [...],
        'data': [
            [...],  # predictions for antibiotic 1
            [...],  # predictions for antibiotic 2
            ...
        ]
    }
    """
    data = []

    for antibiotic in antibiotics:
        row = []
        for model_name in model_names:
            try:
                value = get_prediction(model_name, antibiotic, file)
            except Exception:
                logger.exception('Prediction failed for model=%s, antibiotic=%s', model_name, antibiotic)
                value = 'NO_RESULT'

            row.append(value)
        data.append(row)

    return {
        'models': model_names,
        'antibiotics': antibiotics,
        'data': data,
    }