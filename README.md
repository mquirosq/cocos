# tfg
Framework to easily access and offer prediction models for predicting antibiotic resistance

## Add new prediction models

To add a new prediction model include a folder under `ai_models/` with the model name and the required files. Minimal layout and rules:

- Folder layout

```
ai_models/<model_name>/
	pesos/
		<antibiotic>.pt       # model weights per-antibiotic
	model_classes.py          # model definition and adapter implementation
```

- The weights file must be named with the antibiotic it targets, for example `ampicillin.pt`.
- `model_classes.py` should expose the model architecture and the adapter class that implements the prediction interface. The adapter should be designed to load the appropriate weights based on the antibiotic specified during initialization.

- Use the provided decorator to register your adapter implementation:

```py
from app.ai_models.registry import register_model

@register_model("model_alias")
class MyAdapter:
	def __init__(self, antibiotic: str):
		...

	def predict(self, sequences):
		...
```

Important: the adapter `__init__` signature should be exactly `__init__(antibiotic: str)`.


An example implementation can be found in `ai_models/base_bakta-50/`.

