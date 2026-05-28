import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payhere_vertext.settings')

app = Celery('payhere_vertext')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
