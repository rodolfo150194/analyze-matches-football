"""
URL configuration for predictions app
"""

from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'predictions'

urlpatterns = [
    path('', RedirectView.as_view(url='/matches/', permanent=False), name='home'),
    path('matches/', views.matches_list, name='matches_list'),
]
