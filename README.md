# cocos

Framework for integrating and deploying antibiotic resistance prediction models in genomic analysis workflows.

COCOS provides a web interface that allows users to process genomic data and obtain antibiotic resistance predictions from multiple registered prediction models. The framework is designed to facilitate the use of research models by users without requiring direct interaction with the underlying machine learning implementations.

---

## Quick Start

### Development Setup

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

The development environment includes:

- Django development server
- PostgreSQL
- Redis
- Celery worker

Access at: `http://localhost:8080`

The development environment mounts the application source code into the containers, so changes to the code are reflected without rebuilding the image.

### Production Deployment

The production environment uses:

                         Nginx
                           │
                           ▼
                       Gunicorn
                           │
                           ▼
                         Django
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          PostgreSQL      Redis       Celery

Nginx is the public entry point and acts as a reverse proxy for the Django application.

The Django/Gunicorn container is not directly exposed to the host.

From `cocos/docker` folder:

```bash
# Configure environment (copy template and fill with real values)
cp ../.env.prod.example ../.env.prod
```

Then edit `.env.prod and` configure the required values. At minimum, production requires:

```
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<strong-secret-key>

DB_NAME=<database-name>
DB_USER=<database-user>
DB_PASSWORD=<strong-password>
DB_HOST=postgres
DB_PORT=5432

POSTGRES_DB=<database-name>
POSTGRES_USER=<database-user>
POSTGRES_PASSWORD=<strong-password>
```

Generate a Django secret key with:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

If email notifications are enabled, configure:

```
SENDGRID_API_KEY=<api-key>
```

The production domain is configured through environment variables:

```
DJANGO_ALLOWED_HOSTS=<domain>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<domain>
```

For example:

```
DJANGO_ALLOWED_HOSTS=cocos.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://cocos.example.com
```

These values depend on the domain assigned to the deployment.

To start the production environment, run:

```
docker compose --env-file ../.env.prod -f docker-compose.prod.yml -p cocos-prod up --build -d
```

The production stack contains:

- `cocos-web` - Django + Gunicorn
- `cocos-worker` - Celery worker
- `cocos-nginx` - Nginx reverse proxy
- `cocos-postgres` - PostgreSQL
- `cocos-redis` - Redis

The application data and uploaded files are stored in Docker volumes.

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
