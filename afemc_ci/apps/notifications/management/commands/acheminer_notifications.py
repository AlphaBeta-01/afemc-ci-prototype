from django.core.management.base import BaseCommand

from apps.notifications.services import acheminer_notifications_en_attente


class Command(BaseCommand):
    help = "Achemine les notifications en attente."

    def handle(self, *args, **options):
        envoyees, echecs = acheminer_notifications_en_attente()
        self.stdout.write(self.style.SUCCESS(
            f'{envoyees} notification(s) envoyée(s), {echecs} échec(s).'))
