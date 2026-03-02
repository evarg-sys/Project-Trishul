from .celery import app as celery_app

__all__ = ('celery_app',) # making sure Celery starts up everytime Django starts up 