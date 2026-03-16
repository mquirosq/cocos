from django.urls import path
from . import views

app_name = "conversion"

urlpatterns = [
    path("", views.conversion_task_ui, name="conversion_task_ui"),
    path('feature-parser/', views.parse_feature_file, name='parse_feature_file'),
    path("annotation/", views.annotation_task, name="annotation_task"),
    path("sequencing/", views.sequencing_task, name="sequencing_task"),
    path("annotation/<str:job_id>/", views.annotation_from_sequencing_task, name="annotation_from_sequencing_task"),
    # Task list and task detail routes (moved from model)
    path('tasks/', views.task_list_view, name='task_list'),
    path('tasks/<int:task_id>/', views.task_status_view, name='task_status'),
    path('tasks/<int:task_id>/download/', views.download_json_view, name='download_json'),
]
