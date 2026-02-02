from django.urls import path
from . import views

urlpatterns = [
    path('', views.task_list_view, name='task_list'),
    path('<int:task_id>/', views.task_status_view, name='task_status'),
    path('<int:task_id>/download/', views.download_json_view, name='download_json'),
]
