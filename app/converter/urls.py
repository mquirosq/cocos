from django.urls import path
from . import views

app_name = "converter"

urlpatterns = [
    path("", views.external_task_ui, name="external_task_ui"),
]
