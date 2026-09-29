from django.urls import path
from . import views

app_name = 'prediction'

urlpatterns = [
    path('prediction/', views.prediction_ui, name='prediction'),
    path('prediction/matrix/', views.make_prediction_view, name='prediction_matrix'),
    path('prediction/matrix/csv/', views.prediction_csv_from_matrix_view, name='prediction_csv_from_matrix'),
]
