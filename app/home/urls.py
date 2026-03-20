from django.urls import include, path
from . import views

urlpatterns = [
    path(
        'accounts/',
        include(
            (
                [
                    path('', include('django.contrib.auth.urls')),
                    path('register/', views.register, name='register'),
                ],
                'accounts',
            ),
            namespace='accounts',
        ),
    ),
    path('', views.home, name='home'),
    path('delete_all_tasks/', views.delete_all_tasks, name='delete_all_tasks'),  # For testing purposes
]