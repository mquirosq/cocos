from django.apps import AppConfig
from django.conf import settings


class ConverterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'converter'

    def ready(self):
        if settings.DEBUG:
            try:
                import redis
                from celery import current_app

                # Purga colas de Celery en desarrollo
                current_app.control.purge()

                # Conectar a Redis y borrar tareas de Celery
                r = redis.from_url(settings.CELERY_BROKER_URL)
                for key in r.scan_iter("celery*"):
                    r.delete(key)
                for key in r.scan_iter("celery-task-meta*"):
                    r.delete(key)
            except Exception as e:
                pass
