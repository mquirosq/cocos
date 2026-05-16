FROM node:20-alpine AS frontend

WORKDIR /frontend

COPY app/package.json app/package-lock.json ./
RUN npm ci

COPY app/ ./
RUN npm run build:css


FROM python:3.11-slim

# Python no genera archivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Python no hace buffering de stdout/stderr
ENV PYTHONUNBUFFERED=1 

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bring compiled Tailwind + daisyUI stylesheet into Django static files.
COPY --from=frontend /frontend/static/css/tailwind.css /app/app/static/css/tailwind.css

# Collect static files for Django
RUN python manage.py collectstatic --noinput

# Crear un usuario no-root llamado 'app'
RUN addgroup --system app && adduser --system --ingroup app app
RUN chown -R app:app /app

# Ejecutar como usuario no-root por seguridad
USER app
