from typing import Any, Dict


class BaseModelInterface:
    """Lightweight adapter interface for prediction models.

    Actual model adapters in ai_models should implement these methods.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

    def load(self):
        raise NotImplementedError()
