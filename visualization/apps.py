# visualization/apps.py

from django.apps import AppConfig
from django.db.models.signals import post_migrate

class VisualizationConfig(AppConfig):
    name = 'visualization'

    def ready(self):
        from django.dispatch import receiver
        from django.core.signals import request_started

        @receiver(request_started)
        def load_dash_app(sender, **kwargs):
            from visualization.dash_apps import visualization_dashboard
            from visualization.dash_apps import watch_list
            
