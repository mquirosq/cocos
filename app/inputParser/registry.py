"""Model registry utilities.

Holds the global `MODEL_REGISTRY` and helper decorators/accessors used by
model adapter implementations and services.
"""
import inspect

# Registry mapping lowercase name -> adapter class
MODEL_REGISTRY = {}

def _validate_adapter_init(cls) -> None:
    """Ensure adapter `__init__` accepts an `antibiotic` parameter.

    This enforces a minimal constructor contract so callers can reliably
    instantiate adapters.
    """
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
    """Decorator to register a model adapter class.

    If `name` is omitted the class' `__name__` lowercased is used.
    Validates adapter constructor signature on registration.
    """
    def _decorator(cls):
        _validate_adapter_init(cls)
        key = (name or cls.__name__).lower()
        MODEL_REGISTRY[key] = cls
        return cls
    return _decorator

def get_model_adapter_class(name: str):
    """Return the registered model adapter class for `name` (case-insensitive), or None."""
    if not name:
        return None
    return MODEL_REGISTRY.get(name.lower())

def list_registered_models():
    """Return a list of registered model keys."""
    return list(MODEL_REGISTRY.keys())
