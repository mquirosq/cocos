# cocos

Framework to easily access and offer prediction models for predicting antibiotic resistance

## One-command setup (Windows)

From the `cocos` folder run:

```powershell
.\setup.ps1
```

This single command installs:

- Python dependencies from `requirements.txt`
- Frontend dependencies (`tailwindcss` + `daisyui`) from `app/package.json`
- Compiled CSS output at `app/static/css/tailwind.css`

## Database and Docker

The project now uses PostgreSQL by default (SQLite is no longer the runtime database).

Environment variables in `.env`:

- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_CONN_MAX_AGE`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (used by Docker postgres service)

For direct host execution (outside Docker), override `DB_HOST` to `localhost` if needed.

First Docker build can take a long time because ML dependencies (notably `torch`) are large. After the first successful build, subsequent runs should be much faster due to Docker layer cache.

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

### Testing

To run tests:

```bash
python manage.py test
```

To run tests for a specific app:

```bash
python manage.py test notifications
```
