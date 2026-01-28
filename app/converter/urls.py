from django.urls import path
from . import views

app_name = "converter"

urlpatterns = [
    path("", views.external_task_ui, name="external_task_ui"),
    path("status/<int:task_id>/", views.task_status, name="task_status"),
]
