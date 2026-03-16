"""Model registry utilities. Allow registering model adapter classes with a simple decorator and retrieving them by name."""
import inspect

# Registry mapping lowercase name -> adapter class
MODEL_REGISTRY = {}

def _validate_adapter_init(cls) -> None:
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        raise TypeError(f"Cannot inspect __init__ of adapter {cls!r}")

    params = [p for p in sig.parameters.values() if p.name != 'self']
    names = {p.name for p in params}
    if 'antibiotic' not in names:
        raise TypeError(
            f"Adapter {cls.__name__} must accept an 'antibiotic' parameter in __init__"
        )


def register_model(name: str = None):
    def _decorator(cls):
        _validate_adapter_init(cls)
        key = (name or cls.__name__).lower()
        MODEL_REGISTRY[key] = cls
        return cls
    return _decorator

def get_model_adapter_class(name: str):
    if not name:
        return None
    return MODEL_REGISTRY.get(name.lower())

def list_registered_models():
    return list(MODEL_REGISTRY.keys())
