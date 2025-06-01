# visualization/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.visualization_view, name='visualization_home'),
]