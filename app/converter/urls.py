from django.urls import path
from . import views

app_name = "converter"

urlpatterns = [
    path("", views.conversion_task_ui, name="conversion_task_ui"),
    path("annotation/", views.annotation_task, name="annotation_task"),
    path("sequencing/", views.sequencing_task, name="sequencing_task"),
]
