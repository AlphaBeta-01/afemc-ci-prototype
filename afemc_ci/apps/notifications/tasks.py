"""Tâches planifiées d'acheminement."""
from .services import acheminer_notifications_en_attente

try:
    from celery import shared_task
except ImportError:                       # Celery facultatif en développement
    def shared_task(fonction):
        return fonction


@shared_task
def acheminer():
    envoyees, echecs = acheminer_notifications_en_attente()
    return {'envoyees': envoyees, 'echecs': echecs}
