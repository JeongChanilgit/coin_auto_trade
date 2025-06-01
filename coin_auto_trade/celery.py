from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coin_auto_trade.settings')

app = Celery('coin_auto_trade')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks(['trade.tasks'])
