from django.urls import path
from . import views

app_name = 'prediction'

urlpatterns = [
    path('', views.prediction_view, name='prediction'),
]
