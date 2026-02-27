import os
from celery import Celery

# we have the default Django settings rn
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'disaster_backend.settings')

app = Celery('disaster_backend')

# Load config from Django settings, using CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')


app.autodiscover_tasks()

#so basically telling Celery, get your setting from django and find tasks automatically