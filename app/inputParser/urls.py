from django.urls import path
from . import views

app_name = 'inputParser'

urlpatterns = [
    path('prediction/', views.prediction_view, name='prediction'),
]
