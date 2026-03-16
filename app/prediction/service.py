from .registry import get_model_adapter_class

def get_prediction(model_name: str, antibiotic: str, file_upload) -> float:
    model_cls = get_model_adapter_class(model_name)
    if not model_cls:
        raise ValueError(f'Model {model_name} not found in registry.')

    adapter = model_cls(antibiotic=antibiotic)

    adapter.load()
    return adapter.predict(file_upload)
