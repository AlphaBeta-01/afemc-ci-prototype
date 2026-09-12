from .services import executer_detection as _executer

try:
    from celery import shared_task
except ImportError:
    def shared_task(fonction):
        return fonction


@shared_task
def executer_detection():
    return _executer()
