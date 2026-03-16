"""
Lightweight Celery task module for the `prediction` app.

This module exists so Celery's `include=[...]` can import `prediction.tasks`.
Add actual async tasks here if/when prediction needs background jobs.
"""
from celery import shared_task

@shared_task(bind=True)
def noop_ping(self):
    """Simple task used to verify Celery can import this module."""
    return "pong"
