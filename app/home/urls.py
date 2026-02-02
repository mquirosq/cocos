from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('delete_all_tasks/', views.delete_all_tasks, name='delete_all_tasks'),  # For testing purposes
]