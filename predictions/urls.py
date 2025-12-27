"""
URL configuration for predictions app
"""

from django.urls import path
from django.views.generic import RedirectView
from django.http import JsonResponse
from . import views

app_name = 'predictions'

def health_check(request):
    """Simple health check endpoint for Docker/Dokploy"""
    from django.conf import settings
    import os

    return JsonResponse({
        'status': 'healthy',
        'debug': settings.DEBUG,
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'host_header': request.get_host(),
        'env_allowed_hosts': os.getenv('ALLOWED_HOSTS', 'NOT_SET'),
    })

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('', RedirectView.as_view(url='/matches/', permanent=False), name='home'),
    path('matches/', views.matches_list, name='matches_list'),
]
