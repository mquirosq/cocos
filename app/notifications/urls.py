from django.urls import path

from notifications import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notifications_view, name='list'),
    path('read-all/', views.mark_all_notifications_read_view, name='mark_all_read'),
    path('<int:notification_id>/read/', views.mark_notification_read_view, name='mark_read'),
]
