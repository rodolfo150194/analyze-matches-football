"""
URL configuration for predictions app
"""

from django.urls import path
from . import views

app_name = 'predictions'

urlpatterns = [
    path('matches/', views.matches_list, name='matches_list'),
]
