# visualization/views.py

from django.shortcuts import HttpResponse
from .dash_app import app
from django_plotly_dash import DjangoDash

# Dash 앱을 Django에 연결
def visualization_view(request):
    return HttpResponse("Dash")
