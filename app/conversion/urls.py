from django.urls import path
from . import views

app_name = "conversion"

urlpatterns = [
    path("assembly/", views.assembly_ui, name="assembly_ui"),
    path("assembly/run/", views.assembly_task, name="assembly_run"),
    path("annotation/", views.annotation_ui, name="annotation_ui"),
    path("annotation/from-fasta/", views.annotation_task, name="annotation_from_fasta"),
    path("annotation/from-json/", views.parse_feature_file, name="annotation_from_json"),
    path("annotation/from-job/<str:job_id>/", views.annotation_from_assembly_task, name="annotation_from_job"),
    path('tasks/', views.task_list_view, name='task_list'),
    path('tasks/<int:task_id>/', views.task_status_view, name='task_status'),
    path('tasks/<int:task_id>/rename/', views.rename_process_view, name='rename_process'),
    path('tasks/<int:task_id>/download/', views.download_json_view, name='download_json'),
    path('tasks/<int:task_id>/download-fasta/', views.download_fasta_view, name='download_fasta'),
]
