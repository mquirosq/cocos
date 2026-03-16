from .registry import get_model_adapter_class

def get_prediction(model_name: str, antibiotic: str, file_upload) -> float:
    """
    Get the predicted probability of resistance for a given model, antibiotic, and file upload.
    Args:
        model_name: name of the model to use for prediction (e.g. 'BaselineMLP')
        antibiotic: name of the antibiotic (e.g. 'ampicillin')
        file_upload: a FileUpload instance containing the gene data to be parsed for prediction
    Returns:
        A float representing the predicted probability of resistance.
    """
    model_cls = get_model_adapter_class(model_name)
    if not model_cls:
        raise ValueError(f'Model {model_name} not found in registry.')

    adapter = model_cls(antibiotic=antibiotic)

    adapter.load()
    return adapter.predict(file_upload)