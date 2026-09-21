from django.urls import path
from .views import pipeline, status

app_name = "conversion"

urlpatterns = [
    path("assembly/", pipeline.assembly_ui, name="assembly_ui"),
    path("assembly/run/", pipeline.assembly_task, name="assembly_run"),
    path("annotation/", pipeline.annotation_ui, name="annotation_ui"),
    path("annotation/from-fasta/", pipeline.start_annotation_task, name="start_annotation_task"),
    path("annotation/from-json/", pipeline.parse_feature_file, name="annotation_from_json"),
    path('tasks/', status.task_list_view, name='task_list'),
    path('tasks/<int:task_id>/', status.task_status_view, name='task_status'),
    path('tasks/<int:task_id>/rename/', status.rename_process_view, name='rename_process'),
    path('tasks/<int:task_id>/download/', status.download_json_view, name='download_json'),
    path('tasks/<int:task_id>/download-fasta/', status.download_fasta_view, name='download_fasta'),
]
