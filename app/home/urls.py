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
]