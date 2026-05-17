"""Model registry utilities. Allow registering model adapter classes with a simple decorator and retrieving them by name."""
import inspect
from pathlib import Path

MODEL_REGISTRY = {
    # 'model_name': ModelAdapterClass,
}

MODEL_ANTIBIOTICS = {
    # 'model_name': ['antibiotic1', 'antibiotic2', ...],
}

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
        base_dir = Path(__file__).resolve().parents[1]
        weights_dir = base_dir / 'ai_models' / key / 'weights'
        MODEL_REGISTRY[key] = cls
        MODEL_ANTIBIOTICS[key] = _compute_model_supported_antibiotics(weights_dir)
        return cls
    return _decorator

def get_model_adapter_class(name: str):
    key = name.lower() if name else ''
    if key not in MODEL_REGISTRY:
        raise ValueError(f"Model '{name}' not found in registry.")
    return MODEL_REGISTRY[key]

# ---- Public API for views
def list_registered_models():
    return list(MODEL_REGISTRY.keys())

def get_model_supported_antibiotics(name: str):
    """Return list of antibiotic names available for a given registered model."""
    return MODEL_ANTIBIOTICS.get(name.lower(), [])

def list_all_antibiotics():
    """Return sorted list of all antibiotic names available across all registered models."""
    antibiotics = set()
    for ab_list in MODEL_ANTIBIOTICS.values():
        antibiotics.update(ab_list)
    return sorted(antibiotics)

# ---- Internal utilities
def _compute_model_supported_antibiotics(weights_dir: str):
    """
    Compute the list of antibiotic names available for a given registered model.
    """
    if weights_dir.exists() and weights_dir.is_dir():
        return sorted({p.stem for p in weights_dir.glob('*.pt')})
    else:
        return []