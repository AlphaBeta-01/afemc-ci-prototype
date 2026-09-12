"""Planification des traitements automatisés (§ 5.6.1)."""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

app = Celery('afemc_ci')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'detection-quotidienne-des-retards': {
        'task': 'apps.relances.tasks.executer_detection',
        'schedule': crontab(hour=2, minute=0),
    },
    'acheminement-des-notifications': {
        'task': 'apps.notifications.tasks.acheminer',
        'schedule': crontab(minute='*/15'),
    },
    'synthese-hebdomadaire-responsables': {
        'task': 'apps.dashboard.tasks.envoyer_synthese',
        'schedule': crontab(day_of_week=1, hour=7, minute=0),
    },
}
