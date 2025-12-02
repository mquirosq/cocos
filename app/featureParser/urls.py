from django.urls import path
from . import views

urlpatterns = [
    path('', views.parse_feature_file, name='parse_feature_file'),
]