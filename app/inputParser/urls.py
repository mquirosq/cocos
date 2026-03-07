from django.urls import path
from . import views

app_name = 'inputParser'

urlpatterns = [
    path('presence-test/', views.presence_test, name='presence_test'),
    path('presence-columns-test/', views.presence_from_columns_test, name='presence_from_columns_test'),
    path('prediction/', views.prediction_view, name='prediction'),
]
