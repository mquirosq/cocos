# cocos

Framework to easily access and offer prediction models for predicting antibiotic resistance.

---

## Quick Start

### Development Setup (Windows)

From the `cocos` folder run:

```powershell
python setup.py
```

This installs:

- Python dependencies from `requirements.txt`
- Frontend dependencies (`tailwindcss` + `daisyui`) from `app/package.json`
- Compiled CSS output at `app/static/css/tailwind.css`

Then start the dev server:

```bash
cd docker
docker compose -f docker-compose.yml up
```

Access at: `http://localhost:8080`

### Production Deployment (Docker)

From `cocos/docker` folder:

```bash
# Configure environment (copy template and fill with real values)
cp ../.env.prod.example ../.env.prod
# Edit .env.prod with production credentials

# Deploy
docker compose -f docker-compose.prod.yml up --build
```

Access at: `http://localhost` (port 80)

---

## Environment Configuration

### Development (`.env`)

- `DB_HOST=localhost` (PostgreSQL on host)
- `DJANGO_DEBUG=1`

### Production (`.env.prod`)

- `DB_HOST=cocos-postgres` (Docker service name)
- `DJANGO_DEBUG=0`
- **MUST SET SECURELY:**
  - `DJANGO_SECRET_KEY` - Generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
  - `POSTGRES_PASSWORD` - Strong, random password
  - `DB_PASSWORD` - Same as POSTGRES_PASSWORD
  - `SENDGRID_API_KEY` - If using email notifications

---

## Database & Docker

**Environment variables:**

- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_CONN_MAX_AGE`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (Docker postgres service)

**First build** can take time due to large ML dependencies (`torch`, etc.). Subsequent runs use Docker layer cache.

---

## Add New Prediction Models

Add a folder under `ai_models/` with required structure:

```
ai_models/<model_name>/
├── weights/
│   ├── <antibiotic>.pt      # model weights per-antibiotic
│   └── ...
└── model_classes.py         # model definition & adapter
```

**Rules:**

- Weight files must be named after the antibiotic (e.g., `amikacin.pt`)
- `model_classes.py` must implement adapter with `__init__(antibiotic: str)` signature
- Use decorator to register:

```python
from app.ai_models.registry import register_model

@register_model("my_model")
class MyAdapter:
    def __init__(self, antibiotic: str):
        # Load weights/<antibiotic>.pt
        pass

    def predict(self, sequences):
        # Return predictions
        pass
```

See `ai_models/base_bakta_50/` for example.

---

## Testing

Run all tests:

```bash
python manage.py test
```

Run tests for specific app:

```bash
python manage.py test notifications
```
